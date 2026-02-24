"""
Mock Underwriting Client.

Purpose:
- Provides a fake underwriting integration to allow development/testing without
  Old Mutual underwriting endpoints.
- Does NOT make network calls.
- Returns a simulated quote response.

Usage:
- Wired in src/api/main.py during development
- Called by UnderwritingFlow via the UnderwritingClient interface

Behavior guidelines:
- create_quote(...) should return quote_id, premium, currency, and decision status
- Should allow testing of both approval and rejection edge cases if needed

Swap:
Replace with the real HTTP underwriting client in clients/real_http/underwriting.py
when underwriting endpoints and payload formats are confirmed.
"""
