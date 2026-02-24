"""
Product catalogue contracts.

Defines the structure of product information used by the chatbot, e.g.:
- product_id, name, category
- description, benefits, eligibility, links
- metadata needed for product discovery and card generation

These contracts must be used by both:
- clients/mocks/local_product_catalogues.py (local data source for development)
- clients/real_http/zoho_product_catalogues.py (Zoho / OM catalogue source when available)

Why:
- Prevents hardcoding product IDs/categories in flow logic
- Makes it easy to reload/update product data without rebuilding the system
- Supports fast re-indexing/re-embedding of product content in the vector database
"""
