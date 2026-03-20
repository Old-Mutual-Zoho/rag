# Zoho AI Chatbot — Backend Pending Tasks

**Last updated:** 19 March 2026
**Repo:** `zoho/rag/`

---

## High Priority — SalesIQ Ecosystem Integration

### 1. Webhook Payload & Response Transformation (US-001, US-004)
- **File:** `src/api/endpoints/main.py`
- **Why:** The LLM internally outputs plain-text or custom dictionary formats. However, SalesIQ strictly requires its proprietary JSON schema structure to render rich UI natively. If the response isn't formatted exactly right, the chat widget will crash or show nothing to the user.
- **Task:** Map our internal response objects to the strictly required SalesIQ JSON format.
- **Code Snippet (SalesIQ Text + Buttons Example Response):**
  ```python
  @app.post("/webhook/salesiq")
  async def salesiq_webhook(payload: dict):
      visitor_id = payload.get("visitor", {}).get("id")
      message = payload.get("message", {}).get("text")
      
      # ... run RAG / LLM agent ...
      
      # Must return structured SalesIQ JSON:
      return {
          "action": "reply",
          "replies": [
              {
                  "text": "I can help with that. Which product are you interested in?",
                  "suggestions": [
                      {"text": "Travel Insurance"},
                      {"text": "Personal Accident"}
                  ]
              }
          ]
      }
  ```

### 2. Zoho CRM Push (Lead Generation) (US-007)
- **File:** `src/integrations/zoho/zoho_chat_service.py`
- **Why:** Human sales teams live inside Zoho CRM. If the bot generates quotes or underwriting profiles but doesn't sync them as native CRM Leads, the entire downstream sales pipeline breaks and potential revenue is lost.
- **Task:** Push conversation data to CRM Leads when a user asks for a quote.
- **Code Snippet (CRM API Payload):**
  ```python
  def sync_lead_to_crm(self, phone: str, name: str, product: str, quote_amount: float):
      url = f"{self.crm_base_url}/Leads"
      payload = {
          "data": [
              {
                  "Last_Name": name,
                  "Phone": phone,
                  "Lead_Source": "Chatbot",
                  "Description": f"Interested in {product}. Quoted: {quote_amount}"
              }
          ]
      }
      requests.post(url, json=payload, headers=self._auth_headers())
  ```

### 3. Zoho Desk Integration (Agent Handoff) (US-009, US-012)
- **File:** `src/api/endpoints/main.py`
- **Why:** When customers get frustrated, stuck, or attempt to file high-risk claims, the AI must instantly transfer the chat to a live human operator via Zoho Desk to protect the brand and resolve the issue. Text fallback is not enough.
- **Task:** When an escalation occurs, forward the chat to a live agent in SalesIQ/Desk natively instead of just replying with text.
- **Code Snippet (SalesIQ Forward Action):**
  ```python
  if confidence < 0.6 or requires_human:
      # Tell SalesIQ to forward to a real operator natively
      return {
          "action": "forward",
          "replies": ["I'm connecting you to a human agent who can help."]
      }
  ```

---

## Security & Infrastructure Upgrades

### 4. Webhook Origin Validation (Signature Check) (US-018)
- **File:** `src/api/endpoints/main.py`
- **Why:** Without strict signature validation, anyone on the open internet can POST directly to the webhook URL. This would allow an attacker to endlessly burn through expensive OpenAI API tokens (a "Denial of Wallet" attack) and corrupt the production analytics database with garbage data.
- **Task:** Validate the `X-ZOHO-SIGNATURE` header so attackers cannot spam the NLP API.
- **Code Snippet (FastAPI Middleware/Dependency):**
  ```python
  import hmac
  import hashlib

  def verify_zoho_signature(request: Request):
      payload_body = await request.body()
      signature = request.headers.get("X-ZOHO-SIGNATURE")
      
      expected_sig = hmac.new(
          settings.ZOHO_WEBHOOK_SECRET.encode(),
          msg=payload_body,
          digestmod=hashlib.sha256
      ).hexdigest()
      
      if not hmac.compare_digest(expected_sig, signature):
          raise HTTPException(status_code=403, detail="Invalid signature")
  ```

### 5. PII Encryption at Rest (US-018)
- **File:** `src/database/models.py`
- **Why:** Personal Accident and Serenicare insurance applications collect highly sensitive data (National IDs, physical passports, emergency contacts). If the Postgres DB is ever compromised, failing to encrypt this PII at rest violates POPIA compliance and results in massive financial penalties.
- **Task:** Encrypt National IDs and phone numbers in the Postgres DB using SQLAlchemy `TypeDecorator`.
- **Code Snippet (SQLAlchemy Encryption):**
  ```python
  from sqlalchemy.types import TypeDecorator, String
  from cryptography.fernet import Fernet

  cipher = Fernet(settings.DB_ENCRYPTION_KEY)

  class EncryptedString(TypeDecorator):
      impl = String

      def process_bind_param(self, value, dialect):
          if value is not None:
              return cipher.encrypt(value.encode()).decode()
          return value

      def process_result_value(self, value, dialect):
          if value is not None:
              return cipher.decrypt(value.encode()).decode()
          return value

  # Usage in model:
  class PersonalAccidentApplication(Base):
      ...
      national_id = mapped_column(EncryptedString(255), nullable=True)
  ```

---

## Medium Priority — Missing APIs

### 6. Admin Knowledge Base CRUD API (US-022)
- **File:** `src/api/routers/admin.py` (Create this file)
- **Why:** The frontend Admin Dashboard needs a backend API to upload new product PDFs securely so the RAG vector store stays up-to-date automatically without begging a backend engineer to redeploy the server.
- **Task:** Accept file uploads, save them to disk/S3, and trigger the `src/rag/ingest.py` embeddings pipeline.

### 7. Email & SMS Notification Service (US-021)
- **File:** `src/integrations/notifications.py` (Create this file)
- **Why:** Users paying hundreds of dollars for policies in-chat expect immediate proof of cover. Without this, completing a payment results in total silence—no receipt, no PDF policy document. This completely undermines trust.
- **Task:** Send policy PDFs after payment success via async Celery/BackgroundTask.
- **Code Snippet (Async Email Task):**
  ```python
  import smtplib
  from email.message import EmailMessage

  async def send_policy_email(user_email: str, pdf_path: str):
      msg = EmailMessage()
      msg['Subject'] = 'Your Old Mutual Policy Document'
      msg['From'] = 'noreply@oldmutual.com'
      msg['To'] = user_email
      
      with open(pdf_path, 'rb') as f:
          msg.add_attachment(f.read(), maintype='application', subtype='pdf', filename='Policy.pdf')
          
      with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
          server.login(settings.SMTP_USER, settings.SMTP_PASS)
          server.send_message(msg)
  ```

### 8. Chat History Auto-Loading (Returning Users) (US-020)
- **File:** `src/chatbot/state_manager.py`
- **Why:** Returning customers will be extremely frustrated if the bot forgets they received a quote from it two days ago. Initializing the agent memory with past sessions creates a seamless, personalized experience.
- **Task:** Before calling LangChain LLM, query the DB for the visitor's past 3 quotes and inject them into the `SystemMessage` so the bot has memory.
