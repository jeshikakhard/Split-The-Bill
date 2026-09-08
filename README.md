# SplitBill AI

Turn a restaurant bill photo into a fair, itemized split between 2-3 people.

## Problem

A group eats out together. Everyone ordered different things, some dishes
were shared, and the bill has GST, a service charge, and sometimes a
discount. Splitting it "equally" is fast but unfair - the person who had
one coffee ends up subsidizing the person who ordered biryani.

## Solution

SplitBill AI reads a photo of the bill with a vision AI model, lets you
review and correct anything it misread, then asks who ate what. It then
computes a mathematically correct, itemized amount per person - with tax,
service charge and discount distributed **proportionally** to what each
person actually consumed, not divided equally.

**There is no chatbot.** Upload a photo, add 2-3 members, tick who ate
what, get a breakdown.

## Features

- Vision-based bill extraction (Google Gemini) with per-field confidence
  scores.
- Pydantic validation so malformed AI output never crashes the app.
- A mandatory human review step - every extracted field is editable.
- 2-3 members, per-item assignment (single person, shared, or everyone).
- Proportional GST/tax, service charge, and discount allocation.
- All money math done in Python `Decimal` with deterministic rounding
  reconciliation (allocated amounts always sum exactly to the target).
- Bill consistency warnings (e.g. printed total doesn't match subtotal +
  tax + service - discount).
- Demo Mode: the entire workflow runs with a bundled sample bill, no API
  key required.
- Handles blurry/unreadable fields, missing tax/service/discount, API
  failures, and user edits without crashing.

## Demo & 5 Pre-Loaded Sample Bills

SplitBill AI includes **5 realistic restaurant receipt scenarios** (both high-resolution PNG receipt images and structured JSON datasets in `sample_bills/`) so you can test the entire application end-to-end without real physical bills or an API key:

1. 🍲 **Indore Spice Kitchen** (`bill_1_indore_spice`): Chicken Biryani, Paneer Pizza, Coke — Subtotal ₹1180, GST ₹118, Service Charge ₹59 ➔ **Total ₹1357.00**
2. ☕ **Urban Brew Cafe & Roastery** (`bill_2_urban_cafe`): Cappuccino, Avocado Toast, Cheesecake, Cold Brew — Subtotal ₹1140, GST ₹57, Service Charge ₹114 ➔ **Total ₹1311.00**
3. 🍕 **Bella Italia Trattoria** (`bill_3_bella_italia`): Pizza, Pasta, Garlic Bread, Tiramisu, Iced Tea — Subtotal ₹1690, 10% Discount ₹169, GST ₹76.05, Service Charge ₹152.10 ➔ **Total ₹1749.15**
4. 🥞 **Dakshin Tiffin Room** (`bill_4_south_indian`): Special Masala Dosa, Ghee Podi Idli, Medu Vada, Filter Coffee — Subtotal ₹640, GST ₹32 ➔ **Total ₹672.00**
5. 🍔 **Smash Burger Co.** (`bill_5_burger_co`): Double Bacon Burgers, Nashville Chicken Burger, Truffle Fries, Shakes — Subtotal ₹1560, GST ₹78, Service Charge ₹78 ➔ **Total ₹1716.00**

You can either:
- Select any bill in the **"5 Pre-loaded Example Bills"** dropdown on Step 1 to load it instantly.
- Download any of the generated PNG receipts from the sidebar or preview expander and upload them directly into the file uploader.

## Architecture

```
Image ──► extractor.py (Gemini vision) ──► raw JSON
                                              │
                                              ▼
                                   models.py (Pydantic validation)
                                              │
                                              ▼
                              app.py: Human Review screen (edit fields)
                                              │
                                              ▼
                        app.py: Add members + assign items ("who ate what")
                                              │
                                              ▼
                     calculator.py (Decimal-only financial math + rounding)
                                              │
                                              ▼
                         app.py: Final per-person breakdown + reconciliation
```

Each file has one job:

- **`app.py`** - Streamlit UI, 4-step workflow, session state, error display.
- **`models.py`** - Pydantic models (`Bill`, `BillItem`, confidence models).
  All numeric parsing failures degrade to `None`/defaults instead of raising.
- **`extractor.py`** - the *only* file that talks to Gemini. Returns a
  validated `Bill` or raises `ExtractionError`. Also loads the demo bill.
- **`calculator.py`** - the *only* file that does money math. Pure functions
  over `Decimal` values and plain Python data; no UI or AI imports.
- **`utils.py`** - formatting, confidence badges, input validation helpers.

## How It Works

1. **Upload** - user uploads a photo, or loads the demo bill.
2. **Extract** - `extractor.py` sends the image to Gemini with a prompt that
   explicitly forbids it from inventing values or splitting the bill; it
   returns structured JSON with a confidence score per field.
3. **Validate** - `models.py` parses that JSON into a `Bill`/`BillItem`
   Pydantic model. Unreadable/missing numeric fields become `None` (or a
   safe default) rather than crashing the app.
4. **Review** - every field is rendered as an editable input, next to a
   colour-coded confidence badge. Nothing is calculated yet.
5. **Confirm** - the user-edited values become the source of truth for all
   further steps.
6. **Assign** - user adds 2-3 members and multiselects who shared each item.
7. **Calculate** - `calculator.py` computes the split (see below) and a
   reconciliation check against the printed total.
8. **Results** - per-person itemized breakdown, plus bill-level totals and
   any consistency warnings.

## Financial Calculation Logic

For each bill item:

1. Its total is split **equally** among the members assigned to it (1, 2,
   3, or all members).
2. Each person's **gross consumption** = sum of their item shares.
3. **Discount** is allocated proportionally to gross consumption:
   `person_discount = discount * (person_gross / total_gross)`.
4. **Net consumption** = gross consumption - discount share.
5. **Tax** and **service charge** are each allocated proportionally to
   **net consumption** (i.e. after discount - this mirrors how most POS
   systems compute GST on the discounted subtotal):
   `person_tax = tax * (person_net / total_net)`.
6. **Final amount** = net consumption + tax share + service charge share.

Example (bundled demo bill, GST = ₹118, service = ₹59, no discount):

| Person  | Consumption | Tax share | Service share | Final |
|---------|-------------|-----------|----------------|-------|
| Jeshika | ₹550        | ₹55.00    | ₹27.50         | ₹632.50 |
| Rahul   | ₹300        | ₹30.00    | ₹15.00         | ₹345.00 |
| Priya   | ₹330        | ₹33.00    | ₹16.50         | ₹379.50 |

Sum = ₹1357.00, matching the printed total exactly.

### Rounding

All amounts are `Decimal`, quantized to 2 decimal places. Equal item splits
and proportional allocations both use a **largest-remainder reconciliation
pass**: round every share down/up to the cent, sum them, and if there's a
leftover cent (from rounding drift) assign it deterministically so the
shares always sum *exactly* to the target amount. This is unit-tested for
both split types.

### Bill consistency checks

Before showing results, the app compares:
- line-item sum vs. printed subtotal
- `subtotal - discount + tax + service_charge` vs. the printed grand total

If either differs by more than ₹1, a warning is shown with the exact
difference. The printed total is **never silently changed** - the user can
correct it in the Review step if they trust their own read of the bill more
than the AI's.

## Why LLM Is Not Used For Financial Calculations

The vision model is good at *perception* - reading messy, printed text and
numbers off a photo - but LLM output is not guaranteed to be arithmetically
exact or reproducible. Money math must be:

- **Deterministic** - the same inputs always produce the same output.
- **Reproducible** - a court, a friend, or a unit test can re-derive it.
- **Testable** - you can write exact assertions against it.
- **Exact** - `0.1 + 0.2` floating point drift is unacceptable when it's
  someone's money.

So the architecture strictly separates concerns: **AI = perception**,
**Pydantic = structured validation**, **human = verification/correction**,
**Python `Decimal` = financial calculation**. The LLM never sees the
per-person split and is never asked to compute one.

## Tech Stack

Python 3.11+, Streamlit, Pydantic v2, Google GenAI SDK (`google-genai`,
Gemini vision), Python `Decimal`, pytest.

## Project Structure

```
splitbill-ai/
├── app.py                     # Streamlit UI (4-step workflow + aesthetics)
├── models.py                  # Pydantic models (Bill, BillItem, validations)
├── extractor.py               # Gemini vision extraction + Demo Mode
├── calculator.py              # Pure Decimal-based financial calculation engine
├── utils.py                   # Formatting, currency cleaning, confidence badges
├── requirements.txt
├── pytest.ini                 # Pytest configuration with pythonpath
├── .env.example
├── .gitignore
├── README.md
├── tests/
│   ├── test_calculator.py          # 17 financial math & allocation tests
│   ├── test_models.py              # 9 Pydantic validation & degradation tests
│   └── test_utils_and_extractor.py # 8 extractor, utils & 5-bill integrity tests
├── sample_bills/
│   ├── generate_bills.py           # Generator script for receipt PNGs & JSONs
│   ├── bill_1_indore_spice.png / .json  # Bill 1 (North Indian & Pizza)
│   ├── bill_2_urban_cafe.png / .json    # Bill 2 (Cafe & Roastery)
│   ├── bill_3_bella_italia.png / .json  # Bill 3 (Italian & 10% Discount)
│   ├── bill_4_south_indian.png / .json  # Bill 4 (South Indian Breakfast)
│   ├── bill_5_burger_co.png / .json     # Bill 5 (Burgers & Shakes)
│   ├── demo_bill.json              # Default demo dataset
│   └── sample_bill.png             # Default sample receipt image
└── assets/
    └── README.md
```

## Installation

```bash
git clone <your-repo-url>
cd splitbill-ai
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Environment Variables

```bash
cp .env.example .env
# then edit .env and set:
# GEMINI_API_KEY=your_key_here
# GEMINI_MODEL=gemini-2.0-flash
```

No key? Just use **Demo Mode** in the app - everything else works.

## Running Locally

```bash
streamlit run app.py
```

Open the URL Streamlit prints (usually `http://localhost:8501`).

## Testing

```bash
pytest -q
```

Covers: single/2-person/3-person item allocation, proportional GST/service
charge/discount, Decimal rounding reconciliation, end-to-end total
reconciliation, Pydantic validation of malformed/missing fields, and
detection of an incorrect printed total.

## Edge Cases Handled

- Blurry image / unreadable field → AI returns `null`, Pydantic defaults it,
  UI highlights it as low confidence and editable.
- Missing tax, service charge, or discount → default to ₹0, math still
  correct.
- Quantity > 1, shared items, single-person items, all-members items.
- Incorrect printed total → detected and shown as a warning + non-zero
  "difference" metric; user can correct it.
- User edits any AI value → the edited value is what flows into the split.
- Rounding residuals → reconciled deterministically, tested.
- Item with no assigned person → blocked at the Assign step (Calculate
  button stays disabled with a clear error).
- API key missing / API call fails / malformed AI JSON → caught as
  `ExtractionError`, shown as a friendly message, Demo Mode still available.

## Design Decisions

- Tax/service charge are allocated on **net** (post-discount) consumption,
  not gross - documented explicitly so the policy is unambiguous and
  auditable.
- Equal-split and proportional-split both use the same largest-remainder
  rounding strategy for consistency.
- `calculator.py` takes plain `Decimal`/`str`/`list` arguments rather than
  Pydantic models directly, so the core money logic has zero UI/AI coupling
  and is trivially unit-testable.
- The printed total is treated as a fact to reconcile *against*, never
  silently overwritten by computed values.

## Limitations

- Extraction quality depends on photo clarity and Gemini's OCR/vision
  accuracy; very low-quality photos will need more manual correction in
  Review.
- Only supports 2-3 members per the spec (not an arbitrary group size).
- No persistence - state lives only in the Streamlit session; refreshing
  the page starts over.
- Single currency symbol (₹) is used for display; no multi-currency
  handling.

## Future Improvements

- Multi-currency support.
- Export the final breakdown as PDF/image to share in a group chat.
- Support splitting across more than 3 members.
- Optional persistence of past splits (still without a chat interface).
