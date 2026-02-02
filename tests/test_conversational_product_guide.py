import pytest

from src.chatbot.flows.router import ChatRouter
from src.chatbot.modes.conversational import ConversationalMode
from src.chatbot.state_manager import StateManager
from src.database.postgres import PostgresDB
from src.database.redis import RedisCache


class DummyRAG:
    async def retrieve(self, query: str, filters=None, top_k=None):
        return [{"payload": {"text": "stub"}}]

    async def generate(self, query: str, context_docs, conversation_history):
        return {"answer": f"ANSWER: {query}", "confidence": 0.5, "sources": []}


class DummyGuided:
    async def process(self, *args, **kwargs):
        raise AssertionError("guided.process should not be called")

    async def start_flow(self, *args, **kwargs):
        raise AssertionError("guided.start_flow should not be called for learn intent")


class DummyGuidedReturnsForm:
    async def process(self, *args, **kwargs):
        raise AssertionError("guided.process should not be called in this test")

    async def start_flow(self, flow_name: str, session_id: str, user_id: str, initial_data=None):
        assert flow_name == "journey"
        assert (initial_data or {}).get("product_flow") == "travel_insurance"
        return {
            "mode": "guided",
            "flow": flow_name,
            "step": 0,
            "response": {"type": "form", "message": "FORM"},
            "data": None,
        }


class DummyMatcher:
    def match_products(self, query: str, top_k: int = 3):
        # Return a travel insurance-like product match with URL
        return [
            (
                1.0,
                0,
                {
                    "product_id": "website:product:travel/travel-insurance",
                    "name": "Travel Insurance",
                    "category_name": "Travel",
                    "sub_category_name": "Travel",
                    "url": "https://www.oldmutual.co.ug/",
                },
            )
        ][:top_k]


@pytest.mark.asyncio
async def test_tell_me_about_travel_insurance_stays_conversational_and_suggests_sections():
    db = PostgresDB()
    redis = RedisCache()
    sm = StateManager(redis, db)

    # Create a session to hold context
    user = db.get_or_create_user(phone_number="256700000000")
    session_id = sm.create_session(str(user.id))

    conv = ConversationalMode(DummyRAG(), DummyMatcher(), sm)
    router = ChatRouter(conv, DummyGuided(), sm, DummyMatcher())

    out = await router.route("hi, tell me about travel insurance", session_id, str(user.id))

    assert out["mode"] == "conversational"
    assert "should i share the benefits" in out["response"].lower()
    assert out.get("suggested_action") is None


@pytest.mark.asyncio
async def test_product_guide_button_action_returns_section_answer():
    db = PostgresDB()
    redis = RedisCache()
    sm = StateManager(redis, db)

    user = db.get_or_create_user(phone_number="256700000000")
    session_id = sm.create_session(str(user.id))

    conv = ConversationalMode(DummyRAG(), DummyMatcher(), sm)

    # Prime context by asking about travel insurance
    await conv.process("tell me about travel insurance", session_id, str(user.id))

    out = await conv.process("yes", session_id, str(user.id))

    assert out["mode"] == "conversational"
    assert out["response"].startswith("ANSWER:")
    assert "benefits" in out["response"].lower()


@pytest.mark.asyncio
async def test_product_guide_yes_chain_offers_next_section_and_handles_second_yes():
    db = PostgresDB()
    redis = RedisCache()
    sm = StateManager(redis, db)

    user = db.get_or_create_user(phone_number="256700000000")
    session_id = sm.create_session(str(user.id))

    conv = ConversationalMode(DummyRAG(), DummyMatcher(), sm)

    # Start with product explanation (sets pending offer to benefits)
    first = await conv.process("tell me about travel insurance", session_id, str(user.id))
    assert "share the benefits" in first["response"].lower()

    # Yes -> benefits (should now offer eligibility)
    benefits = await conv.process("yes", session_id, str(user.id))
    assert "benefits" in benefits["response"].lower()
    assert "share the eligibility" in benefits["response"].lower()

    # Yes again -> eligibility
    eligibility = await conv.process("yes", session_id, str(user.id))
    assert "eligibility" in eligibility["response"].lower()


@pytest.mark.asyncio
async def test_get_quotation_button_starts_guided_and_returns_form_immediately():
    db = PostgresDB()
    redis = RedisCache()
    sm = StateManager(redis, db)

    user = db.get_or_create_user(phone_number="256700000000")
    session_id = sm.create_session(str(user.id))

    conv = ConversationalMode(DummyRAG(), DummyMatcher(), sm)
    router = ChatRouter(conv, DummyGuidedReturnsForm(), sm, DummyMatcher())

    # Prime topic
    await router.route("tell me about travel insurance", session_id, str(user.id))

    out = await router.route("", session_id, str(user.id), form_data={"action": "get_quotation"})

    assert out["mode"] == "guided"
    assert out["response"]["type"] == "form"
