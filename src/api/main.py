"""
FastAPI application - Main entry point
"""

from dotenv import load_dotenv

load_dotenv()

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from src.chatbot.dependencies import api_key_protection

from src.chatbot.modes.conversational import ConversationalMode
from src.chatbot.modes.guided import GuidedMode
from src.chatbot.product_cards import ProductCardGenerator
from src.chatbot.router import ChatRouter
from src.chatbot.state_manager import StateManager
from src.rag.generate import generate_with_gemini
from src.rag.query import retrieve_context
from src.utils.product_matcher import ProductMatcher
from src.utils.rag_config_loader import load_rag_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Old Mutual Chatbot API",
    description="AI-powered insurance chatbot with conversational and guided modes",
    version="1.0.0",
    dependencies=[Depends(api_key_protection)],  # protect everything by default
)

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

# Initialize databases: use real Postgres/Redis when env is set, else in-memory stubs
if os.getenv("DATABASE_URL") and os.getenv("USE_POSTGRES_CONVERSATIONS", "").lower() in ("1", "true", "yes"):
    from src.database.postgres_real import PostgresDB

    postgres_db = PostgresDB(connection_string=os.environ["DATABASE_URL"])
else:
    from src.database.postgres import PostgresDB

    postgres_db = PostgresDB()

if os.getenv("REDIS_URL"):
    from src.database.redis_real import RedisCache

    redis_cache = RedisCache(url=os.environ["REDIS_URL"])
else:
    from src.database.redis import RedisCache

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

    async def retrieve(self, query: str, filters: Optional[Dict] = None, top_k: Optional[int] = None):
        k = self.cfg.retrieval.top_k if top_k is None else top_k
        return retrieve_context(question=query, cfg=self.cfg, top_k=k, filters=filters)

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
    """Chat request. Use form_data when the frontend submits a step form (e.g. Personal Accident)."""

    message: str = ""
    session_id: Optional[str] = None
    user_id: str
    metadata: Optional[Dict] = None
    form_data: Optional[Dict] = None  # Step form payload; when set, used as user_input in guided flows


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


class CreateSessionRequest(BaseModel):
    """Create a new chatbot session (e.g. when user opens the app)."""

    user_id: str = Field(..., description="User identifier (e.g. phone number or auth id)")


class CreateSessionResponse(BaseModel):
    session_id: str
    user_id: str


class StartGuidedRequest(BaseModel):
    """Start a guided flow (e.g. Personal Accident). Session is created if session_id is omitted."""

    flow_name: str = Field(..., description="Flow id, e.g. 'personal_accident'")
    user_id: str
    session_id: Optional[str] = None
    initial_data: Optional[Dict] = Field(default_factory=dict, description="Optional pre-filled data for the flow")


# ============================================================================
# ENDPOINTS
# ============================================================================


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {"service": "Old Mutual Chatbot API", "status": "healthy", "version": "1.0.0", "timestamp": datetime.now().isoformat()}


@app.get("/health", tags=["Health"])
async def health_check():
    """Detailed health check (Postgres, Redis)."""
    return {"status": "healthy", "database": {"postgres": "connected", "redis": redis_cache.ping()}, "timestamp": datetime.now().isoformat()}


async def _handle_chat_message(request: ChatMessage, router: ChatRouter, db: PostgresDB) -> ChatResponse:
    """Shared logic for chat message. In conversational mode uses same RAG retrieval as run_rag (config top_k, synonyms, re-ranking)."""
    # Resolve external identifier (e.g. phone) to internal user UUID so session/conversation creation never hits FK violation
    user = db.get_or_create_user(phone_number=request.user_id)
    internal_user_id = str(user.id)

    session_id = request.session_id
    if not session_id:
        session_id = state_manager.create_session(internal_user_id)

    # Route message (form_data from frontend is used as user_input in guided flows)
    # Conversational path uses APIRAGAdapter.retrieve() with cfg.retrieval.top_k, synonym expansion, re-ranking
    response = await router.route(
        message=request.message or "",
        session_id=session_id,
        user_id=internal_user_id,
        form_data=request.form_data,
    )

    # Save message to database
    session = state_manager.get_session(session_id)
    if session:
        user_content = json.dumps(request.form_data) if request.form_data else request.message
        db.add_message(
            conversation_id=session["conversation_id"],
            role="user",
            content=user_content,
            metadata=request.metadata or {},
        )
        resp_val = response.get("response")
        if isinstance(resp_val, dict):
            assistant_content = resp_val.get("response") or resp_val.get("message") or str(resp_val)
        else:
            assistant_content = str(resp_val)
        db.add_message(
            conversation_id=session["conversation_id"],
            role="assistant",
            content=assistant_content,
            metadata={"mode": response.get("mode")},
        )

    return ChatResponse(response=response, session_id=session_id, mode=response.get("mode", "conversational"), timestamp=datetime.now().isoformat())


# ---------- API router (prefix /api) ----------
api_router = APIRouter()  # app-level dependency covers these too now


@api_router.post("/session", response_model=CreateSessionResponse, tags=["Sessions"])
async def create_session(
    body: CreateSessionRequest,
    db: PostgresDB = Depends(get_db),
):
    """Create a new chat session. Returns session_id for later requests."""
    try:
        user = db.get_or_create_user(phone_number=body.user_id)
        session_id = state_manager.create_session(str(user.id))
        return CreateSessionResponse(session_id=session_id, user_id=body.user_id)
    except Exception as e:
        logger.error(f"Error creating session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/session/{session_id}")
async def get_session_state(session_id: str):
    """Return current session state for the frontend (mode, flow, step, step name)."""
    try:
        session = state_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        step = session.get("current_step", 0)
        step_name = None
        steps_total = None
        current_flow = session.get("current_flow")
        if current_flow == "personal_accident":
            from src.chatbot.flows.personal_accident import PersonalAccidentFlow

            step_names = PersonalAccidentFlow.STEPS
            step_name = step_names[step] if step < len(step_names) else None
            steps_total = len(step_names)
        elif current_flow == "motor_private":
            from src.chatbot.flows.motor_private import MotorPrivateFlow

            step_names = MotorPrivateFlow.STEPS
            step_name = step_names[step] if step < len(step_names) else None
            steps_total = len(step_names)
        elif current_flow == "serenicare":
            from src.chatbot.flows.serenicare import SerenicareFlow

            step_names = SerenicareFlow.STEPS
            step_name = step_names[step] if step < len(step_names) else None
            steps_total = len(step_names)
        return {
            "session_id": session_id,
            "mode": session.get("mode", "conversational"),
            "current_flow": session.get("current_flow"),
            "current_step": step,
            "step_name": step_name,
            "steps_total": steps_total,
            "collected_keys": list((session.get("collected_data") or {}).keys()),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.post("/chat/start-guided", tags=["Chat"])
async def start_guided_body(
    body: StartGuidedRequest,
    router: ChatRouter = Depends(get_router),
    db: PostgresDB = Depends(get_db),
):
    """Start a guided flow. If session_id is omitted, a new session is created."""
    try:
        session_id = body.session_id
        user = db.get_or_create_user(phone_number=body.user_id)
        internal_user_id = str(user.id)
        if not session_id:
            session_id = state_manager.create_session(internal_user_id)
        response = await router.guided.start_flow(
            flow_name=body.flow_name,
            session_id=session_id,
            user_id=internal_user_id,
            initial_data=body.initial_data or {},
        )
        return {"session_id": session_id, **response}
    except Exception as e:
        logger.error(f"Error starting guided flow: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


def _build_flow_schema(flow_id: str) -> Dict:
    """Build step and form schema for a guided flow. Raises KeyError for unknown flow_id."""
    if flow_id == "personal_accident":
        from src.chatbot.flows.personal_accident import (
            PERSONAL_ACCIDENT_COVERAGE_PLANS,
            PERSONAL_ACCIDENT_RISKY_ACTIVITIES,
            PersonalAccidentFlow,
        )

        steps = []
        for i, name in enumerate(PersonalAccidentFlow.STEPS):
            entry = {"index": i, "name": name}
            if name == "personal_details":
                entry["form"] = {
                    "type": "form",
                    "fields": [
                        {"name": "surname", "label": "Surname", "type": "text", "required": True},
                        {"name": "first_name", "label": "First Name", "type": "text", "required": True},
                        {"name": "middle_name", "label": "Middle Name", "type": "text", "required": False},
                        {"name": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                        {"name": "email", "label": "Email Address", "type": "email", "required": True},
                        {"name": "mobile_number", "label": "Mobile Number", "type": "tel", "required": True},
                        {"name": "national_id_number", "label": "National ID Number", "type": "text", "required": True},
                        {"name": "nationality", "label": "Nationality", "type": "text", "required": True},
                        {"name": "tax_identification_number", "label": "Tax ID", "type": "text", "required": False},
                        {"name": "occupation", "label": "Occupation", "type": "text", "required": True},
                        {"name": "gender", "label": "Gender", "type": "select", "options": ["Male", "Female", "Other"], "required": True},
                        {"name": "country_of_residence", "label": "Country of Residence", "type": "text", "required": True},
                        {"name": "physical_address", "label": "Physical Address", "type": "text", "required": True},
                    ],
                }
            elif name == "next_of_kin":
                entry["form"] = {
                    "type": "form",
                    "fields": [
                        {"name": "nok_first_name", "label": "First Name", "type": "text", "required": True},
                        {"name": "nok_last_name", "label": "Last Name", "type": "text", "required": True},
                        {"name": "nok_middle_name", "label": "Middle Name", "type": "text", "required": False},
                        {"name": "nok_phone_number", "label": "Phone Number", "type": "tel", "required": True},
                        {"name": "nok_relationship", "label": "Relationship", "type": "text", "required": True},
                        {"name": "nok_address", "label": "Address", "type": "text", "required": True},
                        {"name": "nok_id_number", "label": "ID Number", "type": "text", "required": False},
                    ],
                }
            elif name == "previous_pa_policy":
                entry["form"] = {
                    "type": "yes_no_details",
                    "question_id": "previous_pa_policy",
                    "details_field": {"name": "previous_insurer_name", "show_when": "yes"},
                }
            elif name == "physical_disability":
                entry["form"] = {
                    "type": "yes_no_details",
                    "question_id": "physical_disability",
                    "details_field": {"name": "disability_details", "show_when": "no"},
                }
            elif name == "risky_activities":
                entry["form"] = {
                    "type": "checkbox",
                    "options": PERSONAL_ACCIDENT_RISKY_ACTIVITIES,
                    "other_field": {"name": "risky_activity_other"},
                }
            elif name == "coverage_selection":
                entry["form"] = {
                    "type": "options",
                    "options": [{"id": p["id"], "label": p["label"], "sum_assured": p["sum_assured"]} for p in PERSONAL_ACCIDENT_COVERAGE_PLANS],
                }
            elif name == "upload_national_id":
                entry["form"] = {"type": "file_upload", "field_name": "national_id_file_ref", "accept": "application/pdf"}
            elif name in ("premium_and_download", "choose_plan_and_pay"):
                entry["form"] = {"type": "premium_summary", "actions": ["view_all_plans", "proceed_to_pay"]}
            steps.append(entry)
        return {"flow_id": "personal_accident", "steps": steps}

    if flow_id == "motor_private":
        from src.chatbot.flows.motor_private import (
            MOTOR_PRIVATE_ADDITIONAL_BENEFITS,
            MOTOR_PRIVATE_EXCESS_PARAMETERS,
            MotorPrivateFlow,
        )

        steps = []
        for i, name in enumerate(MotorPrivateFlow.STEPS):
            entry = {"index": i, "name": name}
            if name == "vehicle_details":
                entry["form"] = {
                    "type": "form",
                    "fields": [
                        {"name": "vehicle_make", "label": "Choose vehicle make", "type": "select", "required": True},
                        {"name": "year_of_manufacture", "label": "Year of manufacture", "type": "text", "required": True},
                        {"name": "cover_start_date", "label": "Cover start date", "type": "date", "required": True},
                        {"name": "rare_model", "label": "Is the car a rare model?", "type": "radio", "options": ["Yes", "No"], "required": True},
                        {"name": "valuation_done", "label": "Has the vehicle undergone valuation?", "type": "radio",
                         "options": ["Yes", "No"], "required": True},
                        {"name": "vehicle_value", "label": "Value of Vehicle (UGX)", "type": "number", "required": True},
                        {"name": "first_time_registration", "label": "First time registration for this type?", "type": "radio",
                         "options": ["Yes", "No"], "required": True},
                        {"name": "car_alarm_installed", "label": "Car alarm installed?", "type": "radio", "options": ["Yes", "No"], "required": True},
                        {"name": "tracking_system_installed", "label": "Tracking system installed?", "type": "radio",
                         "options": ["Yes", "No"], "required": True},
                        {"name": "car_usage_region", "label": "Car usage region", "type": "radio",
                         "options": ["Within Uganda", "Within East Africa", "Outside East Africa"], "required": True},
                    ],
                }
            elif name == "excess_parameters":
                entry["form"] = {"type": "checkbox", "options": MOTOR_PRIVATE_EXCESS_PARAMETERS}
            elif name == "additional_benefits":
                entry["form"] = {"type": "checkbox", "options": MOTOR_PRIVATE_ADDITIONAL_BENEFITS}
            elif name == "benefits_summary":
                entry["form"] = {"type": "benefits_summary"}
            elif name == "premium_calculation":
                entry["form"] = {"type": "premium_summary", "actions": ["edit", "download_quote"]}
            elif name == "about_you":
                entry["form"] = {
                    "type": "form",
                    "fields": [
                        {"name": "first_name", "label": "First Name", "type": "text", "required": True},
                        {"name": "middle_name", "label": "Middle Name (Optional)", "type": "text", "required": False},
                        {"name": "surname", "label": "Surname", "type": "text", "required": True},
                        {"name": "phone_number", "label": "Phone Number", "type": "text", "required": True},
                        {"name": "email", "label": "Email", "type": "email", "required": True},
                    ],
                }
            elif name in ("premium_and_download", "choose_plan_and_pay"):
                entry["form"] = {"type": "premium_summary", "actions": ["edit", "download_quote", "proceed_to_pay"]}
            steps.append(entry)
        return {"flow_id": "motor_private", "steps": steps}

    if flow_id == "serenicare":
        from src.chatbot.flows.serenicare import SERENICARE_OPTIONAL_BENEFITS, SERENICARE_PLANS, SerenicareFlow

        steps = []
        for i, name in enumerate(SerenicareFlow.STEPS):
            entry = {"index": i, "name": name}
            if name == "cover_personalization":
                entry["form"] = {
                    "type": "form",
                    "fields": [
                        {"name": "date_of_birth", "label": "Date of Birth", "type": "date", "required": True},
                        {"name": "include_spouse", "label": "Include Spouse/Partner", "type": "checkbox", "required": False},
                        {"name": "include_children", "label": "Include Child/Children", "type": "checkbox", "required": False},
                        {"name": "add_another_main_member", "label": "Add another main member", "type": "checkbox", "required": False},
                    ],
                }
            elif name == "optional_benefits":
                entry["form"] = {"type": "checkbox", "options": SERENICARE_OPTIONAL_BENEFITS}
            elif name == "medical_conditions":
                entry["form"] = {
                    "type": "radio",
                    "question_id": "medical_conditions",
                    "options": [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
                    "required": True,
                }
            elif name == "plan_selection":
                entry["form"] = {
                    "type": "options",
                    "options": [
                        {"id": p["id"], "label": p["label"], "description": p["description"], "benefits": p["benefits"]}
                        for p in SERENICARE_PLANS
                    ],
                }
            elif name == "about_you":
                entry["form"] = {
                    "type": "form",
                    "fields": [
                        {"name": "first_name", "label": "First Name", "type": "text", "required": True},
                        {"name": "middle_name", "label": "Middle Name (Optional)", "type": "text", "required": False},
                        {"name": "surname", "label": "Surname", "type": "text", "required": True},
                        {"name": "phone_number", "label": "Phone Number", "type": "text", "required": True},
                        {"name": "email", "label": "Email", "type": "email", "required": True},
                    ],
                }
            elif name in ("premium_and_download", "choose_plan_and_pay"):
                entry["form"] = {"type": "premium_summary", "actions": ["view_all_plans", "proceed_to_pay"]}
            steps.append(entry)
        return {"flow_id": "serenicare", "steps": steps}

    raise KeyError(flow_id)


@api_router.get("/flows/{flow_id}/schema", tags=["Guided Flows"])
async def get_flow_schema(flow_id: str):
    """Return step and field schema for a guided flow (personal_accident, motor_private, serenicare)."""
    try:
        return _build_flow_schema(flow_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown flow: {flow_id}")


@api_router.post("/chat/message", response_model=ChatResponse, tags=["Chat"])
async def api_send_message(
    request: ChatMessage,
    router: ChatRouter = Depends(get_router),
    db: PostgresDB = Depends(get_db),
):
    """
    Send a message or form_data (frontend). Uses same RAG retrieval as run_rag:
    config-driven top_k, synonym expansion, re-ranking. Routes to conversational or guided mode.
    """
    try:
        return await _handle_chat_message(request, router, db)
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ---------- Product routes ----------
@api_router.get("/products/list", tags=["Products"])
async def api_list_products(category: Optional[str] = None, matcher: ProductMatcher = Depends(lambda: product_matcher)):
    """List all products. Optional ?category=personal."""
    try:
        if category:
            products = matcher.get_products_by_category(category)
        else:
            products = list(matcher.product_index.values())
        return {"products": products, "count": len(products)}
    except Exception as e:
        logger.error(f"Error listing products: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products/categories", tags=["Products"])
async def api_list_product_categories(matcher: ProductMatcher = Depends(lambda: product_matcher)):
    """List top-level product categories (e.g. personal, business)."""
    try:
        categories = sorted({p.get("category_name") for p in matcher.product_index.values() if p.get("category_name")})
        return {"categories": categories}
    except Exception as e:
        logger.error(f"Error listing product categories: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products/by-id/{product_id:path}", tags=["Products"])
async def api_get_product_by_id(
    product_id: str,
    include_details: bool = False,
    matcher: ProductMatcher = Depends(lambda: product_matcher),
):
    """
    Get product info from chunks: overview, benefits, general. When include_details=true, also returns faq.
    product_id is the full doc_id (e.g. website:product:personal/save-and-invest/sure-deal-savings-plan).
    """
    try:
        product = matcher.get_product_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        sections = _load_product_sections(product_id)
        out = {
            "product_id": product_id,
            "name": product.get("name"),
            "category": product.get("category_name"),
            "subcategory": product.get("sub_category_name"),
            "url": product.get("url"),
            "overview": sections.get("overview", []),
            "benefits": sections.get("benefits", []),
            "general": sections.get("general", []),
        }
        if include_details:
            out["faq"] = sections.get("faq", [])
        return out
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products/by-id/{product_id:path}/details", tags=["Products"])
async def api_get_product_details_by_id(
    product_id: str,
    matcher: ProductMatcher = Depends(lambda: product_matcher),
):
    """Same as by-id with include_details=true: overview, benefits, general, and faq."""
    try:
        product = matcher.get_product_by_id(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        sections = _load_product_sections(product_id)
        return {
            "product_id": product_id,
            "name": product.get("name"),
            "category": product.get("category_name"),
            "subcategory": product.get("sub_category_name"),
            "url": product.get("url"),
            "overview": sections.get("overview", []),
            "benefits": sections.get("benefits", []),
            "general": sections.get("general", []),
            "faq": sections.get("faq", []),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products/{category}", tags=["Products"])
async def api_list_product_subcategories_or_products(category: str, matcher: ProductMatcher = Depends(lambda: product_matcher)):
    """
    List subcategories under a business unit (category), or products if category has none.
    Frontend: if subcategories is non-empty show them; else show products (or 404 if invalid category).
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
        products: List[Dict[str, Any]] = []
        if not subs:
            products = [
                {"product_id": p["product_id"], "name": p["name"], "url": p.get("url")}
                for p in matcher.product_index.values()
                if p.get("category_name", "").lower() == cat_lower
            ]
            if not products:
                raise HTTPException(status_code=404, detail="Category not found or has no products")
        return {"category": category, "subcategories": subs, "products": products}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing category: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products/{category}/{subcategory}", tags=["Products"])
async def api_list_products_in_subcategory(category: str, subcategory: str, matcher: ProductMatcher = Depends(lambda: product_matcher)):
    """List products in a category/subcategory. product_id in each item is the full doc_id for by-id endpoints."""
    try:
        cat_lower = category.lower()
        sub_lower = subcategory.lower()
        items = [
            {"product_id": p["product_id"], "name": p["name"], "url": p.get("url")}
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


@api_router.get("/products/{category}/{subcategory}/{product_slug}", tags=["Products"])
async def api_get_product_structured(
    category: str,
    subcategory: str,
    product_slug: str,
    matcher: ProductMatcher = Depends(lambda: product_matcher),
):
    """Structured product sections (overview, benefits, faq, etc.) by category/subcategory/slug."""
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


@api_router.get("/products/card/{product_id:path}", tags=["Products"])
async def api_get_product_card(product_id: str, include_details: bool = False):
    """Product card (RAG summary). Use by-id when product_id contains slashes."""
    try:
        card = product_card_gen.generate_card(product_id, False)
        if not card:
            raise HTTPException(status_code=404, detail="Product not found")
        if include_details:
            card["details"] = await product_card_gen.get_product_details(product_id)
        return card
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting product: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@api_router.get("/products/card/{product_id:path}/details", tags=["Products"])
async def api_get_product_card_details(product_id: str):
    """Detailed product information (Learn More) via RAG/LLM."""
    try:
        return await product_card_gen.get_product_details(product_id)
    except Exception as e:
        logger.error(f"Error getting product details: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


app.include_router(api_router, prefix="/api")


def _strip_heading_from_text(text: str, heading: str) -> str:
    """
    Remove duplicated heading from the start of text so the API returns
    content-only in "text" when "heading" is already present.
    Handles "Heading\\ncontent", "Q: Heading\\nA: answer" (FAQ), and similar.
    """
    if not text or not heading:
        return text
    t, h = text.strip(), heading.strip()
    if not h:
        return text
    # "Heading\ncontent" or "Heading content"
    if t.lower().startswith(h.lower()):
        rest = t[len(h) :].lstrip("\n\t ")
        if rest.upper().startswith("A:") and "Q:" in t[:4]:
            rest = rest[2:].lstrip()
        return rest if rest else t
    # FAQ: "Q: Heading\nA: answer" -> return just the answer
    q_prefix = "Q: " + h
    if t.lower().startswith(q_prefix.lower()):
        after = t[len(q_prefix) :].lstrip()
        if after.upper().startswith("A:"):
            return after[2:].lstrip()
        return after
    return text


def _load_product_sections(product_id: str) -> Dict[str, List[Dict[str, str]]]:
    """
    Load typed sections for a product from website_chunks.jsonl.
    Each entry's "text" is trimmed so it does not repeat the "heading".
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
            heading = data.get("section_heading") or ""
            raw_text = data.get("text") or ""
            text = _strip_heading_from_text(raw_text, heading)
            entry = {"heading": heading, "text": text}
            sections.setdefault(ctype, []).append(entry)
    return sections


@app.post(
    "/quotes/generate",
    response_model=QuoteResponse,
    tags=["Quotes"],
    dependencies=[Depends(api_key_protection)],
)
async def generate_quote(request: QuoteRequest, db: PostgresDB = Depends(get_db)):
    """Generate an insurance quote from underwriting data."""
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


@app.get(
    "/quotes/{quote_id}",
    tags=["Quotes"],
    dependencies=[Depends(api_key_protection)],
)
async def get_quote(quote_id: str, db: PostgresDB = Depends(get_db)):
    """Get a quote by ID."""
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


@app.get(
    "/sessions/{session_id}/history",
    tags=["Sessions"],
    dependencies=[Depends(api_key_protection)],
)
async def get_conversation_history(session_id: str, limit: int = 50):
    """Get conversation history for a session."""
    try:
        session = state_manager.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = postgres_db.get_conversation_history(session["conversation_id"], limit=limit)

        msg_list = [{"role": msg.role, "content": msg.content, "timestamp": msg.timestamp.isoformat()} for msg in reversed(messages)]
        return {"session_id": session_id, "messages": msg_list}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete(
    "/sessions/{session_id}",
    tags=["Sessions"],
    dependencies=[Depends(api_key_protection)],
)
async def end_session(session_id: str):
    """End a chatbot session."""
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
