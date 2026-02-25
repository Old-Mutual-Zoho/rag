"""
General Info Handler: Scrapes and organizes product definition, benefits, and eligibility into per-product JSON files.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("general_info_handler")

# Dummy function to simulate scraping. Replace with real scraping logic.
def scrape_general_info() -> Dict[str, Dict[str, Any]]:
    # Example structure for demonstration
    return {
        "motor_private": {
            "definition": "Motor Private insurance covers privately owned vehicles against risks such as theft, accident, and fire.",
            "benefits": [
                "Comprehensive coverage for accidents",
                "Theft protection",
                "Fire damage coverage"
            ],
            "eligibility": "Available to individuals with privately registered vehicles."
        },
        "personal_accident": {
            "definition": "Personal Accident insurance provides financial protection in case of accidental injuries or death.",
            "benefits": [
                "Accidental death benefit",
                "Medical expenses coverage",
                "Permanent disability coverage"
            ],
            "eligibility": "Available to individuals aged 18-65."
        },
        # Extra product for testing
        "test_product": {
            "definition": "This is a test product created to verify JSON generation and paths.",
            "benefits": ["Test benefit 1", "Test benefit 2"],
            "eligibility": "Anyone can see this product."
        }
    }

def main():
    # Resolve output folder relative to THIS script
    BASE_DIR = Path(__file__).resolve().parent
    output_dir = BASE_DIR / "product_json"
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Writing JSON files to: {output_dir}")

    product_data = scrape_general_info()
    for product_id, info in product_data.items():
        out_path = output_dir / f"{product_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
        logger.info(f"Created JSON for product: {product_id} -> {out_path}")

    logger.info("All general info JSON files have been written successfully.")

if __name__ == "__main__":
    main()