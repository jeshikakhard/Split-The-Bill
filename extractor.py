"""
extractor.py - the ONLY file that talks to an AI provider.

Responsibility: image -> structured, Pydantic-validated Bill data.
This module NEVER calculates who owes what. It NEVER splits a bill between
people. It only perceives what is printed on the bill image and returns it
as structured data with per-field confidence scores. All financial math
lives in calculator.py.

Uses the current official Google GenAI SDK (`google-genai` package,
`from google import genai`).
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import ValidationError

from models import Bill

# Automatically load environment variables from .env file if present
load_dotenv()

DEMO_BILL_PATH = Path(__file__).parent / "sample_bills" / "demo_bill.json"

EXTRACTION_PROMPT = """You are a bill/receipt understanding system. Look ONLY at the
attached restaurant bill image and extract its structured contents.

Rules you MUST follow:
- Extract only information that is visibly printed and legible on the bill.
- If a field is unreadable, missing, or you are not confident, set it to null.
  Never invent or guess a value.
- Preserve quantities and prices exactly as printed (do not round or "fix" them).
- Clearly distinguish: subtotal, discount, GST/tax, service charge, and the
  final grand total. These are different line items - do not merge them.
- Do NOT calculate anything. Do NOT decide who consumed what. Do NOT split
  the bill between people. Only report what is printed.
- For every extracted field, also give a confidence score from 0.0 to 1.0
  reflecting how legible/certain that value is (not a general vibe - base it
  on print clarity, ambiguity, and whether the digits are fully visible).

Return ONLY valid JSON matching exactly this schema, nothing else:

{
  "restaurant_name": string or null,
  "date": string or null,
  "items": [
    {"name": string, "quantity": number or null, "unit_price": number or null,
     "total": number or null, "confidence": number}
  ],
  "subtotal": number or null,
  "discount": number or null,
  "tax": number or null,
  "service_charge": number or null,
  "total": number or null,
  "field_confidence": {
    "restaurant_name": number, "date": number, "subtotal": number,
    "discount": number, "tax": number, "service_charge": number, "total": number
  },
  "raw_notes": string or null
}
"""


class ExtractionError(Exception):
    """Raised when the AI extraction pipeline cannot produce usable data."""


def get_api_key() -> Optional[str]:
    """Retrieve Gemini API key from environment, .env, or Streamlit secrets."""
    load_dotenv()
    key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not key:
        try:
            import streamlit as st
            if "GEMINI_API_KEY" in st.secrets:
                key = st.secrets["GEMINI_API_KEY"]
            elif "GOOGLE_API_KEY" in st.secrets:
                key = st.secrets["GOOGLE_API_KEY"]
        except Exception:
            pass
    return key


def get_model_name() -> str:
    """Retrieve Gemini model name with sensible default."""
    load_dotenv()
    model = os.environ.get("GEMINI_MODEL")
    if not model:
        try:
            import streamlit as st
            if "GEMINI_MODEL" in st.secrets:
                model = st.secrets["GEMINI_MODEL"]
        except Exception:
            pass
    return model or "gemini-2.0-flash"


SAMPLE_BILLS_DIR = Path(__file__).parent / "sample_bills"
DEMO_BILL_PATH = SAMPLE_BILLS_DIR / "demo_bill.json"

SAMPLE_BILLS = {
    "bill_1_indore_spice": {
        "title": "Indore Spice Kitchen (Biryani, Pizza, Coke)",
        "category": "North Indian & Italian",
        "json_path": SAMPLE_BILLS_DIR / "bill_1_indore_spice.json",
        "img_path": SAMPLE_BILLS_DIR / "bill_1_indore_spice.png",
        "default_members": ["Jeshika", "Rahul", "Priya"],
        "default_assignments": {0: ["Jeshika", "Rahul"], 1: ["Priya"], 2: ["Jeshika", "Priya"]},
    },
    "bill_2_urban_cafe": {
        "title": "Urban Brew Cafe & Roastery (Brunch & Coffee)",
        "category": "Specialty Cafe",
        "json_path": SAMPLE_BILLS_DIR / "bill_2_urban_cafe.json",
        "img_path": SAMPLE_BILLS_DIR / "bill_2_urban_cafe.png",
        "default_members": ["Aarav", "Meera", "Rohan"],
        "default_assignments": {0: ["Aarav", "Meera"], 1: ["Aarav"], 2: ["Meera", "Rohan"], 3: ["Rohan"]},
    },
    "bill_3_bella_italia": {
        "title": "Bella Italia Trattoria (Pizza, Pasta, 10% Discount)",
        "category": "Italian Fine Dining",
        "json_path": SAMPLE_BILLS_DIR / "bill_3_bella_italia.json",
        "img_path": SAMPLE_BILLS_DIR / "bill_3_bella_italia.png",
        "default_members": ["Vikram", "Sneha", "Kabir"],
        "default_assignments": {0: ["Vikram", "Sneha"], 1: ["Kabir"], 2: ["Vikram", "Sneha", "Kabir"], 3: ["Sneha", "Kabir"], 4: ["Vikram", "Sneha"]},
    },
    "bill_4_south_indian": {
        "title": "Dakshin Tiffin Room (Dosas, Idlis, Filter Coffee)",
        "category": "South Indian Breakfast",
        "json_path": SAMPLE_BILLS_DIR / "bill_4_south_indian.json",
        "img_path": SAMPLE_BILLS_DIR / "bill_4_south_indian.png",
        "default_members": ["Karthik", "Ananya", "Dev"],
        "default_assignments": {0: ["Karthik", "Ananya"], 1: ["Dev"], 2: ["Karthik"], 3: ["Karthik", "Ananya", "Dev"]},
    },
    "bill_5_burger_co": {
        "title": "Smash Burger Co. (Burgers, Shakes, Loaded Fries)",
        "category": "American Fast Casual",
        "json_path": SAMPLE_BILLS_DIR / "bill_5_burger_co.json",
        "img_path": SAMPLE_BILLS_DIR / "bill_5_burger_co.png",
        "default_members": ["Riya", "Aditya", "Tanmay"],
        "default_assignments": {0: ["Aditya", "Tanmay"], 1: ["Riya"], 2: ["Riya", "Aditya", "Tanmay"], 3: ["Riya", "Tanmay"]},
    },
}


def load_sample_bill(bill_id: str = "bill_1_indore_spice") -> Bill:
    """Load any of the 5 bundled sample bills by ID."""
    info = SAMPLE_BILLS.get(bill_id, SAMPLE_BILLS["bill_1_indore_spice"])
    with open(info["json_path"], "r", encoding="utf-8") as f:
        data = json.load(f)
    data["is_demo"] = True
    return Bill.model_validate(data)


def load_demo_bill() -> Bill:
    """Load the default bundled demo bill (no API key required)."""
    return load_sample_bill("bill_1_indore_spice")


def _parse_ai_json(text: str) -> dict:
    """
    Parse JSON from AI output, handling markdown fences and arbitrary preamble.
    Raises ExtractionError on failure.
    """
    cleaned = text.strip()
    
    # 1. Direct JSON parse attempt
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 2. Extract from markdown code fence ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. Extract substring between first '{' and last '}'
    first_brace = cleaned.find("{")
    last_brace = cleaned.rfind("}")
    if first_brace != -1 and last_brace > first_brace:
        try:
            return json.loads(cleaned[first_brace:last_brace + 1])
        except json.JSONDecodeError:
            pass

    raise ExtractionError(
        f"AI returned malformed or non-JSON output. Raw snippet: {cleaned[:120]}..."
    )


def extract_bill_from_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> Bill:
    """
    Send the bill image to Gemini and return a validated Bill.

    Raises ExtractionError if the API key is missing, the API call fails,
    or the response cannot be parsed/validated. Callers should catch this
    and fall back to demo mode or show an error - never crash the app.
    """
    api_key = get_api_key()
    if not api_key:
        raise ExtractionError(
            "No GEMINI_API_KEY found in environment or .env file. "
            "Please configure your key or click 'Load Demo Bill' to test SplitBill AI."
        )

    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise ExtractionError(
            "google-genai package is not installed. Run `pip install google-genai`."
        ) from e

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=get_model_name(),
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                EXTRACTION_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
    except Exception as e:
        raise ExtractionError(f"Gemini API call failed: {e}") from e

    text = getattr(response, "text", None)
    if not text:
        raise ExtractionError("Gemini returned an empty response.")

    data = _parse_ai_json(text)

    try:
        return Bill.model_validate(data)
    except ValidationError as e:
        raise ExtractionError(f"AI response failed validation: {e}") from e

