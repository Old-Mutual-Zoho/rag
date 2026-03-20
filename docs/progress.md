# Old Mutual Zoho AI Chatbot — Project Progress Report

**Date:** 19 March 2026
**Based on:** userStories.md mapped against backend + frontend + admin dashboard implementation
**See also:** `pending-tasks_Backend.md` and `pending-tasks_Frontend.md` for detailed task breakdowns

---

## Architecture Context

> **Hybrid Webhook Zobot Approach (Adopted)**
>
> The project has migrated to a SalesIQ Webhook Zobot architecture where:
> - **Zoho SalesIQ** owns the chat UI, widget, visitor tracking, multi-channel, and agent handoff
> - **External Bot (Python / LangChain)** provides the AI brain: RAG, LLM, underwriting, quotation, payment, and policy generation — exposed via webhook
> - **Zoho CRM / Desk / Analytics** handles lead routing, ticketing, and dashboards natively
>
> **Key implication:** The custom `chatbot_interface/` React app is **superseded** by SalesIQ's native widget. Frontend work is now the **admin dashboard** and SalesIQ configuration/branding only.

---

## Summary

| Area | Status | Backend | Frontend / Config |
|------|--------|---------|-------------------|
| 1. SalesIQ Webhook Zobot Setup (US-001) | ~70% | Webhook endpoint built | SalesIQ Zobot config needed |
| 2. Widget Branding & Deployment (US-002) | ~10% | N/A | SalesIQ branding/embed pending |
| 3. Product Discovery via RAG (US-003) | ~85% | RAG pipeline + product catalog done | SalesIQ card formatting needed |
| 4. Product Selection & Guided Flows (US-004) | ~90% | 4 product flows fully built (PA, Travel, Serenicare, Motor) | — |
| 5. Multi-Turn Conversation (US-005) | ~80% | Session management + conversation history done | — |
| 6. Dynamic Recommendation Questions (US-006) | ~80% | Dynamic question engine built | — |
| 7. Lead Visibility in CRM (US-007) | ~30% | Zoho CRM client service exists | SalesIQ→CRM integration pending |
| 8. Quotation & Underwriting (US-008) | ~85% | Premium calc + underwriting service + mock toggle done | — |
| 9. Human Agent Escalation (US-009) | ~50% | Escalation service + DB model built | SalesIQ handoff config pending |
| 10. In-Chat Payment (US-010) | ~75% | Payment service (mobile money) + audit trail done | — |
| 11. Policy Document Generation (US-011) | ~60% | Policy service + PDF generation started | Email/SMS delivery not done |
| 12. CX Agent Visibility — Desk (US-012) | ~10% | N/A | SalesIQ→Desk integration pending |
| 13. User Identity & Session Mgmt (US-013) | ~60% | Session management exists | SalesIQ visitor mapping incomplete |
| 14. Data Consent & Privacy (US-014) | ~20% | Basic consent recording | Full POPIA compliance pending |
| 15. Admin Dashboard (US-015) | ~50% | Metrics service exists | AI Dashboard + Agent Console built |
| 16. Infrastructure & CI/CD (US-016) | ~50% | Docker, Railway, Alembic, GitHub Actions exist | Production hardening pending |
| 17. AI Guardrails & Fallbacks (US-017) | ~70% | Fallback handler + content validator built | Prompt injection detection partial |
| 18. Security Hardening (US-018) | ~40% | Rate limiter exists | Webhook origin validation, PII encryption pending |
| 19. User Feedback (US-019) | ~10% | Not implemented | — |
| 20. Chat History — Returning Users (US-020) | ~50% | Conversation DB supports history lookup | Auto-context loading pending |
| 21. Notifications & Alerts (US-021) | ~20% | Basic structure only | Email/SMS delivery services pending |
| 22. Knowledge Base Management (US-022) | ~30% | Ingest pipeline exists | Admin CRUD UI and versioning pending |
| 23. Multi-Channel (US-023) | ~10% | N/A | SalesIQ WhatsApp/email config pending |
| 24. Multilingual Support (US-024) | ~5% | Not started | — |
| 25. Analytics & Event Tracking (US-025) | ~30% | RAGMetric model + ConversationEvent logging exist | Funnel computation not done |
| 26. E2E Testing & QA (US-026) | ~40% | 28 test files exist | Integration/load/E2E tests missing |

**Overall estimate: ~48% complete**

---

## Sprint-by-Sprint Breakdown

### Sprint 1 — SalesIQ Setup & RAG Foundation

| Story | Status | Notes |
|-------|--------|-------|
| US-001 Webhook Zobot Setup | Partial | Webhook endpoint works, SalesIQ Zobot not configured |
| US-002 Widget Branding | Not started | SalesIQ embed + CSS branding needed |
| US-003 Product Discovery (RAG) | Mostly done | RAG pipeline, vector + keyword search, product cards, scraper |
| US-013 Identity & Session | Partial | Session table exists, SalesIQ visitor mapping incomplete |
| US-014 Data Consent | Partial | Basic consent recording, no full POPIA framework |
| US-016 CI/CD | Partial | Docker + Railway + GitHub Actions, but no staging/prod gating |

### Sprint 2 — Hybrid RAG & Conversational Flow

| Story | Status | Notes |
|-------|--------|-------|
| US-004 Product Selection & Guided Options | Done | 4 product flows with dedicated controllers |
| US-005 Multi-Turn Conversation | Mostly done | Conversation history, context tracking, follow-up manager |
| US-017 AI Guardrails | Mostly done | Fallback handler, content validator, confidence scoring |
| US-018 Security Hardening | Partial | Rate limiter exists, missing webhook signature validation + PII encryption |

### Sprint 3 — Lead Capture & CRM Integration

| Story | Status | Notes |
|-------|--------|-------|
| US-006 Dynamic Questions | Mostly done | `dynamic_question_engine.py` + field filter built |
| US-007 Lead → CRM | Partial | `ZohoChatService` exists but CRM lead push incomplete |
| US-019 User Feedback | Not started | No feedback collection or ratings implemented |

### Sprint 4 — Quotation & Underwriting

| Story | Status | Notes |
|-------|--------|-------|
| US-008 Eligibility & Quotation | Mostly done | Underwriting service + premium calc + mock toggle |
| US-009 Human Escalation | Partial | `EscalationSession` model + escalation service, SalesIQ handoff missing |
| US-020 Returning User History | Partial | DB supports it, auto-context loading on return not built |

### Sprint 5 — Payment & Policy Delivery

| Story | Status | Notes |
|-------|--------|-------|
| US-010 In-Chat Payment | Mostly done | Payment service + mobile money + audit trail |
| US-011 Policy Document | Partial | Policy service + PDF generation started, email/SMS delivery pending |
| US-021 Notifications | Partial | No email/SMS notification orchestration service |

### Sprint 6 — CX Intelligence & Multi-Channel

| Story | Status | Notes |
|-------|--------|-------|
| US-012 CX Agent (Desk) | Not started | Zoho Desk integration not built |
| US-015 Admin Dashboard | Partial | AI Performance Dashboard + Agent Console built, not wired to real metrics API |
| US-022 Knowledge Base Mgmt | Partial | Ingest pipeline works, admin CRUD UI + versioning pending |
| US-023 Multi-Channel | Not started | SalesIQ WhatsApp/email config needed |
| US-024 Multilingual | Not started | No language detection or multilingual RAG |
| US-025 Analytics & Tracking | Partial | RAGMetric + ConversationEvent models exist, funnel computation missing |
| US-026 E2E Testing | Partial | 28 unit test files exist, integration/load/E2E tests missing |

---

## Architecture

| Layer | Technology | Status |
|-------|-----------|--------|
| Chat UI & Widget | Zoho SalesIQ (Webhook Zobot) | Not configured |
| AI Brain | Python + FastAPI + LangChain | Built |
| LLM | OpenAI (GPT-4) | Integrated |
| Vector Store | Embeddings + keyword search | Built |
| RAG Pipeline | Hybrid (vector + keyword) | Built |
| Database | PostgreSQL (SQLAlchemy) + Redis | Built |
| Payment Gateway | Mobile money integration | Built |
| Policy PDF | PDF generation service | Partial |
| CRM Integration | Zoho CRM API via `ZohoChatService` | Partial |
| Desk Integration | Zoho Desk | Not started |
| Admin Dashboard | React + Vite + TailwindCSS | Partial |
| Custom Chat UI | React + Vite (chatbot_interface) | **SUPERSEDED by SalesIQ** |
| CI/CD | GitHub Actions + Docker + Railway | Partial |
| Tests | pytest (28 test files) | Partial |

---

## Codebase Repos

| Repo | Purpose | Path |
|------|---------|------|
| `rag/` | Backend — AI brain, webhook, RAG, business logic | `zoho/rag/` |
| `chatbot_interface/` | **SUPERSEDED** — Custom React chat UI (replaced by SalesIQ widget) | `zoho/chatbot_interface/` |
| `admin_dashboard/` | Admin panel — AI performance, agent console, auth | `zoho/admin_dashboard/` |

---

## Priority Recommendations

### Critical — Architecture Alignment
1. **Configure SalesIQ Webhook Zobot** — register external bot webhook URL, configure greeting, fallback
2. **Embed SalesIQ widget** on website with Old Mutual branding
3. **Deprecate `chatbot_interface/`** — all custom chat UI work is wasted under the SalesIQ model
4. **Format all bot responses as SalesIQ-compatible JSON** (text, buttons, cards, carousels)

### High Priority — Backend Gaps
5. Zoho CRM lead push (enrich + sync leads from conversations)
6. Zoho Desk ticket creation for escalated conversations
7. Email + SMS notification services (policy, payment, escalation events)
8. Webhook origin validation (verify SalesIQ request signatures)
9. PII encryption at rest (AES-256)
10. User feedback collection service

### Medium Priority — Feature Completion
11. Knowledge base admin CRUD + versioning + preview mode
12. Chat history auto-loading for returning visitors
13. Consent management (full POPIA framework)
14. Admin dashboard wiring to real backend metrics API
15. Multi-channel response formatting (WhatsApp/email constraints)

### Lower Priority
16. Multilingual support (language detection + multilingual RAG)
17. Analytics funnel computation
18. Load testing (k6/Artillery for webhook endpoint)
19. E2E test suite covering full purchase journey
20. CI/CD production hardening (staging gate, manual prod approval)

---

## Recent Changes Log

| Date | Change | Repo |
|------|--------|------|
| 19 Mar 2026 | Created progress.md, pending-tasks_Backend.md, pending-tasks_Frontend.md | — |

