"""
Integrations layer.

This package contains all code used to communicate with external systems such as:
- Old Mutual underwriting APIs (quote/premium decisions)
- Payment systems (e.g., Mobile Money / payment gateways)
- Product catalogue sources (Zoho or local product files)

Key rule:
- Chatbot flows MUST NOT call external APIs directly.
- Flows should call integration clients (under src/integrations/clients).
- We use MOCK clients during development and swap to REAL_HTTP clients when APIs are available.

Switching implementations:
- The selection of mock vs real clients should happen in ONE place (src/api/main.py).
"""
