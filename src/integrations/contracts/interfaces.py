"""
Interfaces (behavior contracts).

These interfaces define the methods that the chatbot expects from integrations.
Both MOCK and REAL_HTTP clients must implement the same methods so that:

- We can develop without waiting for real APIs
- We can swap mock -> real implementations without changing chatbot flow code
- We reduce tight coupling between chatbot logic and external dependencies

Examples:
- PaymentFlow calls payment_client.initiate_payment(...)
- During development, payment_client is a MockPaymentClient
- When APIs arrive, payment_client becomes a RealHttpPaymentClient

Important:
- Only the client implementation changes. Flow logic stays the same.
"""
