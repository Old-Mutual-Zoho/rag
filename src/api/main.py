"""
FastAPI application - Main entry point
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List
import logging
from datetime import datetime
from pathlib import Path
import json

# Import our modules
from src.database.postgres import PostgresDB
from src.database.redis import RedisCache
from src.chatbot.state_manager import StateManager
from src.chatbot.router import ChatRouter
from src.chatbot.modes.conversational import ConversationalMode
from src.chatbot.modes.guided import GuidedMode
from src.chatbot.product_cards import ProductCardGenerator
from src.utils.product_matcher import ProductMatcher
from src.utils.rag_config_loader import load_rag_config
from src.rag.query import retrieve_context
from src.rag.generate import generate_with_gemini

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Old Mutual Chatbot API", description="AI-powered insurance chatbot with conversational and guided modes", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

# Initialize databases (singleton pattern)
postgres_db = PostgresDB()
redis_cache = RedisCache()

# Initialize components
state_manager = StateManager(redis_cache, postgres_db)
product_matcher = ProductMatcher()

# Load RAG configuration once per process
rag_cfg = load_rag_config()


class APIRAGAdapter:
    """
    Thin async-compatible wrapper around the existing RAG query pipeline.
    """

    def __init__(self):
        self.cfg = rag_cfg

    async def retrieve(self, query: str, filters: Optional[Dict] = None, top_k: int = 5):
        # Current retrieve_context does not support filters; we ignore them for now.
        return retrieve_context(question=query, cfg=self.cfg, top_k=top_k)

    async def generate(self, query: str, context_docs: List[Dict], conversation_history: List[Dict]):
        """
        Use the configured generation backend (Gemini by default) to
        produce an answer grounded in the retrieved context.
        """
        if not self.cfg.generation.enabled:
            # Fallback: simple extractive answer from context only.
            snippets = []
            for h in context_docs:
                payload = h.get("payload") or {}
                text = (payload.get("text") or "").strip()
                if text:
                    snippets.append(text)
            answer = "\n\n".join(snippets) or "I'm not sure based on the available information."
            return {"answer": answer, "confidence": 0.5, "sources": context_docs}

        if self.cfg.generation.backend == "gemini":
            answer = generate_with_gemini(
                question=query,
                hits=context_docs,
                model=self.cfg.generation.model,
                api_key_env=self.cfg.generation.api_key_env,
            )
            return {"answer": answer, "confidence": 0.7, "sources": context_docs}

        # Unsupported backend
        return {
            "answer": "Generation backend not supported in API adapter.",
            "confidence": 0.0,
            "sources": context_docs,
        }


rag_adapter = APIRAGAdapter()

conversational_mode = ConversationalMode(rag_adapter, product_matcher, state_manager)
guided_mode = GuidedMode(state_manager, product_matcher, postgres_db)
chat_router = ChatRouter(conversational_mode, guided_mode, state_manager, product_matcher)
product_card_gen = ProductCardGenerator(product_matcher, rag_adapter)


def get_db():
    """Dependency for database sessions"""
    return postgres_db


def get_redis():
    """Dependency for Redis cache"""
    return redis_cache


def get_router():
    """Dependency for chat router"""
    return chat_router


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    user_id: str
    metadata: Optional[Dict] = None


class ChatResponse(BaseModel):
    response: Dict
    session_id: str
    mode: str
    timestamp: str


class QuoteRequest(BaseModel):
    product_id: str
    user_id: str
    underwriting_data: Dict


class QuoteResponse(BaseModel):
    quote_id: str
    product_name: str
    monthly_premium: float
    sum_assured: float
    valid_until: str


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"service": "Old Mutual Chatbot API", "status": "healthy", "version": "1.0.0", "timestamp": datetime.now().isoformat()}


@app.get("/health")
async def health_check():
    """Detailed health check"""
    return {"status": "healthy", "database": {"postgres": "connected", "redis": redis_cache.ping()}, "timestamp": datetime.now().isoformat()}


@app.post("/chat/message", response_model=ChatResponse)
async def send_message(request: ChatMessage, router: ChatRouter = Depends(get_router), db: PostgresDB = Depends(get_db)):
    """
    Send a message to the chatbot
    Automatically routes to conversational or guided mode
    """
    try:
        # Get or create session
        session_id = request.session_id

        if not session_id:
            # Create new session
            user = db.get_or_create_user(phone_number=request.user_id)
            session_id = state_manager.create_session(str(user.id))

        # Route message
        response = await router.route(message=request.message, session_id=session_id, user_id=request.user_id)

        # Save message to database
        session = state_manager.get_session(session_id)
        if session:
            db.add_message(conversation_id=session["conversation_id"], role="user", content=request.message, metadata=request.metadata)

            db.add_message(
                conversation_id=session["conversation_id"], role="assistant", content=str(response.get("response", "")), metadata={"mode": response.get("mode")}
            )

        return ChatResponse(response=response, session_id=session_id, mode=response.get("mode", "conversational"), timestamp=datetime.now().isoformat())

    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/start-guided")
async def start_guided_flow(flow_name: str, session_id: str, user_id: str, router: ChatRouter = Depends(get_router)):
    """Start a specific guided flow"""
    try:
        response = await router.guided.start_flow(flow_name=flow_name, session_id=session_id, user_id=user_id)

        return response

    except Exception as e:
        logger.error(f"Error starting guided flow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/list")
async def list_products(category: Optional[str] = None, matcher: ProductMatcher = Depends(lambda: product_matcher)):
    """Get list of products"""
    try:
        if category:
            products = matcher.get_products_by_category(category)
        else:
            products = list(matcher.product_index.values())

        return {"products": products, "count": len(products)}

    except Exception as e:
        logger.error(f"Error listing products: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/categories")
async def list_product_categories(
    matcher: ProductMatcher = Depends(lambda: product_matcher),
):
    """
    List top-level product categories, e.g. 'personal', 'business'.
    """
    try:
        categories = sorted({p.get("category_name") for p in matcher.product_index.values() if p.get("category_name")})
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error listing product categories: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/{category}")
async def list_product_subcategories(
    category: str,
    matcher: ProductMatcher = Depends(lambda: product_matcher),
):
    """
    List subcategories under a given category, e.g. 'personal' -> 'save-and-invest'.
    """
    try:
        cat_lower = category.lower()
        subs = sorted(
            {
                p.get("sub_category_name")
                for p in matcher.product_index.values()
                if p.get("category_name", "").lower() == cat_lower and p.get("sub_category_name")
            }
        )
        if not subs:
            raise HTTPException(status_code=404, detail="Category not found or has no subcategories")
        return {"category": category, "subcategories": subs}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing subcategories: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/{category}/{subcategory}")
async def list_products_in_subcategory(
    category: str,
    subcategory: str,
    matcher: ProductMatcher = Depends(lambda: product_matcher),
):
    """
    List products under a specific category/subcategory combination,
    using the website index doc IDs as product IDs.
    """
    try:
        cat_lower = category.lower()
        sub_lower = subcategory.lower()
        items = [
            {
                "product_id": p["product_id"],
                "name": p["name"],
                "url": p.get("url"),
            }
            for p in matcher.product_index.values()
            if p.get("category_name", "").lower() == cat_lower and p.get("sub_category_name", "").lower() == sub_lower
        ]
        if not items:
            raise HTTPException(status_code=404, detail="No products found for this category/subcategory")
        return {"category": category, "subcategory": subcategory, "products": items}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing products in subcategory: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/products/{product_id}")
async def get_product(product_id: str, include_details: bool = False):
    """Get product information"""
    try:
        card = product_card_gen.generate_card(product_id, include_details)

        if not card:
            raise HTTPException(status_code=404, detail="Product not found")

        return card

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _load_product_sections(product_id: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Helper to load typed sections for a product directly from
    `website_chunks.jsonl`, grouped by `chunk_type`.
    """
    chunks_path = Path(__file__).parent.parent.parent / "data" / "processed" / "website_chunks.jsonl"
    if not chunks_path.exists():
        raise HTTPException(status_code=500, detail="Product chunks file not found")

    sections: Dict[str, List[Dict[str, str]]] = {}
    with open(chunks_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            data = json.loads(line)
            if data.get("type") != "product":
                continue
            if data.get("doc_id") != product_id:
                continue
            ctype = data.get("chunk_type") or "general"
            entry = {
                "heading": data.get("section_heading") or "",
                "text": data.get("text") or "",
            }
            sections.setdefault(ctype, []).append(entry)
    return sections


@app.get("/products/{category}/{subcategory}/{product_slug}")
async def get_product_structured(
    category: str,
    subcategory: str,
    product_slug: str,
    matcher: ProductMatcher = Depends(lambda: product_matcher),
):
    """
    Get structured, typed sections for a single product WITHOUT going
    through RAG/LLM – ideal for guided product discovery flows.

    The `product_slug` is the URL slug, and the underlying product_id /
    doc_id is in the form:
    `website:product:{category}/{subcategory}/{product_slug}`.
    """
    doc_id = f"website:product:{category}/{subcategory}/{product_slug}"
    product = matcher.get_product_by_id(doc_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    sections = _load_product_sections(doc_id)

    return {
        "product_id": doc_id,
        "name": product.get("name"),
        "category": product.get("category_name"),
        "subcategory": product.get("sub_category_name"),
        "url": product.get("url"),
        "overview": sections.get("overview", []),
        "benefits": sections.get("benefits", []),
        "payment_methods": sections.get("payment_methods", []),
        "general": sections.get("general", []),
        "faq": sections.get("faq", []),
    }


@app.get("/products/{product_id}/details")
async def get_product_details(product_id: str):
    """Get detailed product information (Learn More) via RAG/LLM."""
    try:
        details = await product_card_gen.get_product_details(product_id)
        return details

    except Exception as e:
        logger.error(f"Error getting product details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/quotes/generate", response_model=QuoteResponse)
async def generate_quote(request: QuoteRequest, db: PostgresDB = Depends(get_db)):
    """Generate insurance quote"""
    try:
        # This would use the quotation flow
        from src.chatbot.flows.quotation import QuotationFlow

        quotation_flow = QuotationFlow(product_matcher, db)
        quote_data = await quotation_flow._calculate_premium(request.underwriting_data)

        # Save quote to database
        quote = db.create_quote(
            user_id=request.user_id,
            product_id=request.product_id,
            premium_amount=quote_data["monthly_premium"],
            sum_assured=quote_data["sum_assured"],
            underwriting_data=request.underwriting_data,
            pricing_breakdown=quote_data["breakdown"],
        )

        return QuoteResponse(
            quote_id=str(quote.id),
            product_name=quote_data["product_name"],
            monthly_premium=quote_data["monthly_premium"],
            sum_assured=quote_data["sum_assured"],
            valid_until=quote.valid_until.isoformat(),
        )

    except Exception as e:
        logger.error(f"Error generating quote: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/quotes/{quote_id}")
async def get_quote(quote_id: str, db: PostgresDB = Depends(get_db)):
    """Get quote by ID"""
    try:
        quote = db.get_quote(quote_id)

        if not quote:
            raise HTTPException(status_code=404, detail="Quote not found")

        return {
            "quote_id": str(quote.id),
            "product_id": quote.product_id,
            "product_name": quote.product_name,
            "premium_amount": float(quote.premium_amount),
            "sum_assured": float(quote.sum_assured) if quote.sum_assured else None,
            "status": quote.status,
            "valid_until": quote.valid_until.isoformat() if quote.valid_until else None,
            "generated_at": quote.generated_at.isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting quote: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}/history")
async def get_conversation_history(session_id: str, limit: int = 50):
    """Get conversation history"""
    try:
        session = state_manager.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = postgres_db.get_conversation_history(session["conversation_id"], limit=limit)

        return {
            "session_id": session_id,
            "messages": [{"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()} for msg in reversed(messages)],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def end_session(session_id: str):
    """End chatbot session"""
    try:
        state_manager.end_session(session_id)
        return {"message": "Session ended successfully"}

    except Exception as e:
        logger.error(f"Error ending session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STARTUP/SHUTDOWN EVENTS
# ============================================================================


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Starting Old Mutual Chatbot API...")

    # Create database tables if they don't exist
    try:
        postgres_db.create_tables()
        logger.info("Database tables initialized")
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")

    # Test Redis connection
    if redis_cache.ping():
        logger.info("Redis connection successful")
    else:
        logger.warning("Redis connection failed")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down Old Mutual Chatbot API...")
