"""Financial Services domain dataset and scheme eligibility evaluation engine.

Data Source: Official Government of India Financial Inclusion Circulars.
Data Freshness: Stamped as of August 10, 2026.
"""

import asyncio
import logging
from typing import Any

logger = logging.getLogger("agent.scheme_data")

DATA_AS_OF = "10 August 2026 (Official Policy Circular)"

# Comprehensive dataset of Indian Financial Inclusion & Loan Schemes
SCHEMES_DB: dict[str, dict[str, Any]] = {
    "pm_mudra": {
        "name": "Pradhan Mantri MUDRA Yojana (PMMY)",
        "categories": {
            "shishu": {"max_amount": 50000, "label": "Shishu (up to ₹50,000)"},
            "kishore": {
                "min_amount": 50001,
                "max_amount": 500000,
                "label": "Kishore (₹50,001 to ₹5 Lakhs)",
            },
            "tarun": {
                "min_amount": 500001,
                "max_amount": 1000000,
                "label": "Tarun (₹5 Lakhs to ₹10 Lakhs)",
            },
        },
        "min_age": 18,
        "eligible_occupations": [
            "small business owner",
            "trader",
            "shopkeeper",
            "artisan",
            "vendor",
            "micro enterprise",
            "self-employed",
            "services",
            "manufacturing",
        ],
        "documents": [
            "Identity Proof (Aadhaar / Voter ID / Driving License)",
            "Address Proof (Utility Bill / Ration Card / Aadhaar)",
            "Business Establishment Proof or Quotation of items to purchase",
            "Last 6 months Bank Account Statement",
            "2 Recent Passport-size Photographs",
        ],
    },
    "pm_kisan": {
        "name": "PM Kisan Samman Nidhi",
        "benefit": "Direct income support of ₹6,000 per year in 3 equal installments",
        "eligible_occupations": ["farmer", "cultivator", "agriculture"],
        "max_annual_income": 1000000,
        "documents": [
            "Aadhaar Card (Mandatory for biometric/e-KYC verification)",
            "Land Ownership / Title Record (Khatauni / Khasra details)",
            "Active Savings Bank Passbook linked with Aadhaar & NPCI seeding",
            "Mobile number registered with Aadhaar",
        ],
    },
    "pm_svanidhi": {
        "name": "PM Street Vendor's AtmaNirbhar Nidhi (PM SVANidhi)",
        "benefit": "Collateral-free working capital micro-loan up to ₹50,000 with 7% interest subsidy",
        "min_age": 18,
        "eligible_occupations": [
            "vendor",
            "street vendor",
            "hawker",
            "cart owner",
            "cobbler",
            "artisan",
        ],
        "documents": [
            "Certificate of Vending / Identity Card issued by Urban Local Body (ULB)",
            "Letter of Recommendation (LoR) from ULB/TVC (if ID not issued)",
            "Aadhaar Card",
            "Bank account details (Passbook copy)",
        ],
    },
    "standup_india": {
        "name": "Stand-Up India Scheme",
        "benefit": "Bank loans between ₹10 Lakhs and ₹1 Crore for greenfield enterprises",
        "min_age": 18,
        "required_category": ["woman", "sc", "st", "sc/st"],
        "eligible_occupations": [
            "entrepreneur",
            "manufacturing",
            "services",
            "trading",
            "greenfield enterprise",
        ],
        "documents": [
            "Identity & Address Proof (Aadhaar / Voter ID / Passport)",
            "Caste / Category Certificate (for SC/ST applicants)",
            "Detailed Business Project Report (DPR) with financial projections",
            "Proof of Business Premise Ownership / Lease Deed",
            "Last 1 year Personal Bank Statement & IT Returns (if applicable)",
        ],
    },
    "atal_pension": {
        "name": "Atal Pension Yojana (APY)",
        "benefit": "Guaranteed monthly pension of ₹1,000 to ₹5,000 after age 60",
        "min_age": 18,
        "max_age": 40,
        "excludes_income_tax_payers": True,
        "documents": [
            "Aadhaar Card",
            "Savings Bank Account linked with auto-debit authorization",
            "Active Mobile Number",
        ],
    },
}


def _normalize_scheme_key(query: str) -> str | None:
    """Find matching scheme key from raw scheme query string."""
    q = (query or "").lower().strip()
    if "mudra" in q or "pmm" in q:
        return "pm_mudra"
    if "kisan" in q or "pmk" in q or "farm" in q:
        return "pm_kisan"
    if "svanidhi" in q or "vendor" in q or "hawker" in q:
        return "pm_svanidhi"
    if "standup" in q or "stand up" in q or "women loan" in q:
        return "standup_india"
    if "atal" in q or "pension" in q or "apy" in q:
        return "atal_pension"
    return None


async def evaluate_scheme_eligibility(
    scheme_name: str,
    age: int | None = None,
    annual_income: float | None = None,
    occupation: str | None = None,
    category: str | None = None,
    requested_loan_amount: float | None = None,
    simulate_timeout: bool = False,
) -> dict[str, Any]:
    """Evaluates scheme eligibility and returns official document checklist.

    Includes network error / timeout simulation and data timestamping.
    """
    if simulate_timeout:
        # Simulate network delay that times out
        await asyncio.sleep(0.1)
        raise TimeoutError("Government Scheme Portal API connection timed out.")

    scheme_key = _normalize_scheme_key(scheme_name)
    if not scheme_key:
        return {
            "status": "UNKNOWN_SCHEME",
            "data_as_of": DATA_AS_OF,
            "message": f"Scheme '{scheme_name}' not found in active database. Supported schemes: PM Mudra, PM Kisan, PM SVANidhi, Stand-Up India, Atal Pension Yojana.",
            "documents": [],
        }

    scheme = SCHEMES_DB[scheme_key]
    reasons = []
    eligible = True

    # Age checks
    if "min_age" in scheme and age is not None and age < scheme["min_age"]:
        eligible = False
        reasons.append(
            f"Minimum age required is {scheme['min_age']} years (Applicant age: {age})."
        )

    if "max_age" in scheme and age is not None and age > scheme["max_age"]:
        eligible = False
        reasons.append(
            f"Maximum age limit is {scheme['max_age']} years (Applicant age: {age})."
        )

    # Income checks
    if (
        "max_annual_income" in scheme
        and annual_income is not None
        and annual_income > scheme["max_annual_income"]
    ):
        eligible = False
        reasons.append(
            f"Annual income ceiling is ₹{scheme['max_annual_income']:,} (Applicant income: ₹{annual_income:,.0f})."
        )

    # Occupation checks
    if "eligible_occupations" in scheme and occupation:
        occ_lower = occupation.lower().strip()
        matched = any(
            req_occ in occ_lower or occ_lower in req_occ
            for req_occ in scheme["eligible_occupations"]
        )
        if not matched:
            reasons.append(
                f"Target occupation list includes: {', '.join(scheme['eligible_occupations'])}. User listed '{occupation}'."
            )

    # Category checks
    if "required_category" in scheme and category:
        cat_lower = category.lower().strip()
        matched_cat = any(
            req_cat in cat_lower for req_cat in scheme["required_category"]
        )
        if not matched_cat:
            eligible = False
            reasons.append(
                f"Scheme reserved for SC/ST or Women applicants. User category: '{category}'."
            )

    # Loan Amount specific sub-category for Mudra
    tier_info = ""
    if scheme_key == "pm_mudra" and requested_loan_amount:
        if requested_loan_amount <= 50000:
            tier_info = "Category: Shishu (up to ₹50,000)"
        elif requested_loan_amount <= 500000:
            tier_info = "Category: Kishore (₹50,001 to ₹5 Lakhs)"
        elif requested_loan_amount <= 1000000:
            tier_info = "Category: Tarun (₹5 Lakhs to ₹10 Lakhs)"
        else:
            eligible = False
            reasons.append(
                f"Requested loan ₹{requested_loan_amount:,.0f} exceeds PM Mudra maximum limit of ₹10 Lakhs."
            )

    status_str = "ELIGIBLE" if eligible else "PARTIALLY_ELIGIBLE_OR_INELIGIBLE"

    return {
        "status": status_str,
        "scheme_name": scheme["name"],
        "data_as_of": DATA_AS_OF,
        "tier_info": tier_info,
        "reasons": reasons,
        "documents": scheme["documents"],
        "benefit": scheme.get("benefit", "Government financial inclusion scheme"),
    }
