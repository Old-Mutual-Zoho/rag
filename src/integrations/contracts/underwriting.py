"""
Underwriting contracts.

Defines the expected request/response structures for underwriting operations, e.g.:
- submitting user details to underwriting for premium calculation / approval
- receiving quote_id, premium, decision status, and any requirements

These contracts must be used by both:
- clients/mocks/underwriting.py (fake underwriting results for development/testing)
- clients/real_http/underwriting.py (real underwriting API calls when available)

Why:
- Makes quote generation predictable
- Allows flows to continue development without real underwriting endpoints
- Keeps the system loosely coupled and easier to swap to real APIs later
"""
