"""
Payment contracts.

Defines the expected request/response structures for payment operations, e.g.:
- initiating a payment
- checking payment status

These contracts must be used by both:
- clients/mocks/payments.py (fake responses for development/testing)
- clients/real_http/payments.py (real API calls when available)

Why:
- Keeps responses consistent across environments
- Helps prevent rework when the real API arrives
- Allows the chatbot to be tested end-to-end using mocks
"""
