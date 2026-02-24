"""
Real Payments HTTP Client.

Purpose:
- Makes real HTTP requests to the payment system / Old Mutual payment endpoints
- Implements the PaymentClient interface so flows can call it without change

Usage:
- Wired in src/api/main.py when running against real APIs
- Called by PaymentFlow

Implementation notes:
- Use httpx for async requests
- Handle timeouts, retries, and non-200 responses
- Normalize real API responses into our contract response shape

Important:
- Do NOT add HTTP calls inside flows. Keep HTTP logic here.
"""
