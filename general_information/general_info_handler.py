"""
General Info Handler: Scrapes and organizes product definition, benefits, and eligibility into per-product JSON files.
"""
import os
import json
from pathlib import Path
from typing import Dict, Any

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
            "definition": "Personal Accident insurance provides compensation in case of injury, disability, or death caused by accidental events.",
            "benefits": [
                "Accidental death benefit",
                "Permanent disability cover",
                "Medical expense reimbursement"
            ],
            "eligibility": "Open to individuals aged 18-65."
        },
        "serenicare": {
            "definition": "Serenicare is a health insurance plan offering comprehensive medical coverage for individuals and families.",
            "benefits": [
                "Inpatient and outpatient cover",
                "Maternity benefits",
                "Chronic illness management",
                "Emergency evacuation"
            ],
            "eligibility": "Available to individuals and families who meet the insurer's underwriting criteria."
        },
        "travel": {
            "definition": "Travel insurance provides protection against risks such as medical emergencies, trip cancellations, and lost luggage while traveling.",
            "benefits": [
                "Emergency medical cover",
                "Trip cancellation reimbursement",
                "Lost luggage compensation",
                "Personal accident cover"
            ],
            "eligibility": "Open to individuals traveling domestically or internationally, subject to policy terms."
        }
        # Add more products as needed
    }

def main(output_dir: str = "product_json"):
    os.makedirs(output_dir, exist_ok=True)
    product_data = scrape_general_info()
    for product_id, info in product_data.items():
        out_path = Path(output_dir) / f"{product_id}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2, ensure_ascii=False)
    print(f"General info JSON files written to {output_dir}")

if __name__ == "__main__":
    main()
