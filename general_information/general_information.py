# import json
# import logging
# from pathlib import Path
# from fastapi import APIRouter, HTTPException
# from fastapi.responses import JSONResponse

# api = APIRouter()

# @api.get("/general-information", tags=["General Information"])
# async def get_general_information(product: str):
#     logger = logging.getLogger("general_information")
#     logger.info(f"THIS FILE IS AT: {Path(__file__).resolve()}")
#     logger.info(f"General info request for product={product}")

#     # --- Resolve path relative to project root (D:\ZOHO\rag) ---
#     PROJECT_ROOT = Path(__file__).resolve().parents[1]  # Go up one level to reach 'rag'
#     PRODUCT_DIR = PROJECT_ROOT / "general_information" / "product_json"
#     product_file = PRODUCT_DIR / f"{product}.json"

#     logger.info(f"Checking product file path: {product_file}")

#     # Debug: list files in product_json
#     if PRODUCT_DIR.exists():
#         files = [f.name for f in PRODUCT_DIR.iterdir() if f.is_file()]
#         logger.info(f"Files in product_json folder: {files}")
#     else:
#         logger.warning(f"product_json folder does not exist at {PRODUCT_DIR}")

#     # Check if file exists
#     if not product_file.exists():
#         logger.error(f"Product file not found: {product_file}")
#         raise HTTPException(status_code=404, detail="Product information not found")

#     # Load JSON
#     try:
#         with open(product_file, "r", encoding="utf-8") as f:
#             info = json.load(f)
#     except Exception as e:
#         logger.exception(f"Failed to read product file {product_file}")
#         raise HTTPException(status_code=500, detail="Error reading product information")

#     logger.info(f"Successfully served general info for product={product}")
#     return JSONResponse(content=info)