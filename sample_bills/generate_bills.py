"""
generate_bills.py - Generates 5 realistic sample bills (both PNG receipts & JSON data)
for SplitBill AI testing and demonstration without an API key or real paper receipts.
"""

from __future__ import annotations

import json
from pathlib import Path
from PIL import Image, ImageDraw

OUTPUT_DIR = Path(__file__).parent
OUTPUT_DIR.mkdir(exist_ok=True)

BILLS_DATA = [
    {
        "id": "bill_1_indore_spice",
        "title": "Indore Spice Kitchen",
        "address": "Vijay Nagar, Indore, MP - 452010",
        "gstin": "GSTIN: 23AAAAA0000A1Z5",
        "phone": "Phone: +91 731 2555123",
        "date": "01-Sep-2026 19:45",
        "table": "Table #4 | Bill #ISK-89241",
        "items": [
            {"name": "Chicken Biryani", "quantity": 2, "unit_price": 300, "total": 600, "confidence": 0.97},
            {"name": "Coke (330ml)", "quantity": 1, "unit_price": 80, "total": 80, "confidence": 0.95},
            {"name": "Paneer Pizza", "quantity": 1, "unit_price": 500, "total": 500, "confidence": 0.92},
        ],
        "subtotal": 1180,
        "discount": 0,
        "tax": 118,
        "service_charge": 59,
        "total": 1357,
        "notes": "Classic North Indian & Pizza dinner with GST and Service Charge.",
    },
    {
        "id": "bill_2_urban_cafe",
        "title": "Urban Brew Cafe & Roastery",
        "address": "12 Palasia Square, Indore - 452001",
        "gstin": "GSTIN: 23BBBBB1111B2Z6",
        "phone": "Phone: +91 731 4982231",
        "date": "02-Sep-2026 11:15",
        "table": "Table #12 | Bill #UBC-44109",
        "items": [
            {"name": "Cappuccino Grande", "quantity": 2, "unit_price": 180, "total": 360, "confidence": 0.96},
            {"name": "Avocado Sourdough Toast", "quantity": 1, "unit_price": 320, "total": 320, "confidence": 0.94},
            {"name": "Blueberry Cheesecake", "quantity": 1, "unit_price": 280, "total": 280, "confidence": 0.95},
            {"name": "Cold Brew Tonic", "quantity": 1, "unit_price": 180, "total": 180, "confidence": 0.91},
        ],
        "subtotal": 1140,
        "discount": 0,
        "tax": 57,
        "service_charge": 114,
        "total": 1311,
        "notes": "Brunch & specialty cafe bill with 5% GST and 10% Service Charge.",
    },
    {
        "id": "bill_3_bella_italia",
        "title": "Bella Italia Trattoria",
        "address": "Level 2, Phoenix Citadel Mall, Indore",
        "gstin": "GSTIN: 23CCCCC2222C3Z7",
        "phone": "Phone: +91 731 6689000",
        "date": "03-Sep-2026 21:00",
        "table": "Table #08 | Bill #BIT-10294",
        "items": [
            {"name": "Woodfired Margherita Pizza", "quantity": 1, "unit_price": 450, "total": 450, "confidence": 0.98},
            {"name": "Truffle Mushroom Penne", "quantity": 1, "unit_price": 520, "total": 520, "confidence": 0.95},
            {"name": "Cheesy Garlic Bread", "quantity": 1, "unit_price": 180, "total": 180, "confidence": 0.93},
            {"name": "Classic Tiramisu", "quantity": 1, "unit_price": 300, "total": 300, "confidence": 0.94},
            {"name": "Peach Iced Tea", "quantity": 2, "unit_price": 120, "total": 240, "confidence": 0.96},
        ],
        "subtotal": 1690,
        "discount": 169,
        "tax": 76.05,
        "service_charge": 152.10,
        "total": 1749.15,
        "notes": "Italian dining with 10% Happy Hour discount, proportional GST and service charge.",
    },
    {
        "id": "bill_4_south_indian",
        "title": "Dakshin Tiffin Room",
        "address": "55 MG Road, Rajwada, Indore - 452002",
        "gstin": "GSTIN: 23DDDDD3333D4Z8",
        "phone": "Phone: +91 731 2431980",
        "date": "04-Sep-2026 09:30",
        "table": "Table #02 | Bill #DTR-31920",
        "items": [
            {"name": "Special Masala Dosa", "quantity": 2, "unit_price": 120, "total": 240, "confidence": 0.97},
            {"name": "Ghee Podi Idli (4 pcs)", "quantity": 1, "unit_price": 120, "total": 120, "confidence": 0.96},
            {"name": "Medu Vada (2 pcs)", "quantity": 1, "unit_price": 100, "total": 100, "confidence": 0.94},
            {"name": "Madras Filter Coffee", "quantity": 3, "unit_price": 60, "total": 180, "confidence": 0.98},
        ],
        "subtotal": 640,
        "discount": 0,
        "tax": 32,
        "service_charge": 0,
        "total": 672,
        "notes": "Authentic South Indian breakfast with 5% GST and no service charge.",
    },
    {
        "id": "bill_5_burger_co",
        "title": "Smash Burger Co.",
        "address": "Chappan Dukan, New Palasia, Indore",
        "gstin": "GSTIN: 23EEEEE4444E5Z9",
        "phone": "Phone: +91 731 4223901",
        "date": "05-Sep-2026 18:45",
        "table": "Counter #1 | Token #SBC-82",
        "items": [
            {"name": "Double Bacon Smash Burger", "quantity": 2, "unit_price": 350, "total": 700, "confidence": 0.96},
            {"name": "Crispy Nashville Chicken Burger", "quantity": 1, "unit_price": 280, "total": 280, "confidence": 0.95},
            {"name": "Truffle Parmesan Fries", "quantity": 1, "unit_price": 220, "total": 220, "confidence": 0.93},
            {"name": "Salted Caramel Milkshake", "quantity": 2, "unit_price": 180, "total": 360, "confidence": 0.97},
        ],
        "subtotal": 1560,
        "discount": 0,
        "tax": 78,
        "service_charge": 78,
        "total": 1716,
        "notes": "Gourmet burger hangout with 5% GST and 5% Service Charge.",
    },
]


def render_receipt(b: dict) -> Path:
    w, h = 650, 950
    img = Image.new("RGB", (w, h), color=(252, 252, 250))
    draw = ImageDraw.Draw(img)

    # Outer dashed receipt border
    draw.rectangle([(18, 18), (w - 18, h - 18)], outline=(215, 215, 210), width=2)

    def center(y_pos: int, text: str, fill=(30, 30, 30)):
        draw.text((w // 2 - len(text) * 4.5, y_pos), text, fill=fill)

    # Header
    center(45, b["title"].upper())
    center(70, b["address"], fill=(70, 70, 70))
    center(90, f"{b['gstin']} | {b['phone']}", fill=(90, 90, 90))
    center(110, f"Date: {b['date']}", fill=(80, 80, 80))
    center(130, b["table"], fill=(80, 80, 80))

    # Divider
    for x in range(35, w - 35, 14):
        draw.line([(x, 160), (x + 7, 160)], fill=(160, 160, 160), width=1)

    # Table Header
    draw.text((45, 175), "ITEM DESCRIPTION", fill=(40, 40, 40))
    draw.text((340, 175), "QTY", fill=(40, 40, 40))
    draw.text((420, 175), "PRICE", fill=(40, 40, 40))
    draw.text((520, 175), "TOTAL (INR)", fill=(40, 40, 40))

    for x in range(35, w - 35, 14):
        draw.line([(x, 198), (x + 7, 198)], fill=(160, 160, 160), width=1)

    y = 215
    for it in b["items"]:
        draw.text((45, y), it["name"], fill=(25, 25, 25))
        draw.text((350, y), str(it["quantity"]), fill=(25, 25, 25))
        draw.text((425, y), f"{it['unit_price']:.2f}", fill=(25, 25, 25))
        draw.text((535, y), f"{it['total']:.2f}", fill=(25, 25, 25))
        y += 38

    for x in range(35, w - 35, 14):
        draw.line([(x, y + 10), (x + 7, y + 10)], fill=(160, 160, 160), width=1)

    y += 28
    draw.text((330, y), "Subtotal:", fill=(50, 50, 50))
    draw.text((535, y), f"{b['subtotal']:.2f}", fill=(50, 50, 50))

    if b["discount"] > 0:
        y += 32
        draw.text((330, y), "Discount:", fill=(180, 50, 50))
        draw.text((535, y), f"-{b['discount']:.2f}", fill=(180, 50, 50))

    if b["tax"] > 0:
        y += 32
        draw.text((330, y), "GST / Tax:", fill=(50, 50, 50))
        draw.text((535, y), f"{b['tax']:.2f}", fill=(50, 50, 50))

    if b["service_charge"] > 0:
        y += 32
        draw.text((330, y), "Service Charge:", fill=(50, 50, 50))
        draw.text((535, y), f"{b['service_charge']:.2f}", fill=(50, 50, 50))

    for x in range(310, w - 35, 10):
        draw.line([(x, y + 28), (x + 5, y + 28)], fill=(70, 70, 70), width=2)

    y += 42
    draw.text((330, y), "GRAND TOTAL:", fill=(0, 0, 0))
    draw.text((515, y), f"INR {b['total']:.2f}", fill=(0, 0, 0))

    for x in range(35, w - 35, 14):
        draw.line([(x, y + 35), (x + 7, y + 35)], fill=(160, 160, 160), width=1)

    y += 65
    center(y, "Thank you for dining with us!")
    center(y + 22, "Please scan QR code to rate your experience.", fill=(80, 80, 80))
    center(y + 44, "*** Customer Copy ***", fill=(100, 100, 100))

    img_path = OUTPUT_DIR / f"{b['id']}.png"
    img.save(img_path)

    # Save matching JSON for demo loader
    json_path = OUTPUT_DIR / f"{b['id']}.json"
    json_payload = {
        "restaurant_name": b["title"],
        "date": b["date"].split(" ")[0],
        "items": b["items"],
        "subtotal": b["subtotal"],
        "discount": b["discount"],
        "tax": b["tax"],
        "service_charge": b["service_charge"],
        "total": b["total"],
        "field_confidence": {
            "restaurant_name": 0.95,
            "date": 0.92,
            "subtotal": 0.96,
            "discount": 0.90,
            "tax": 0.94,
            "service_charge": 0.91,
            "total": 0.98,
        },
        "raw_notes": b["notes"],
    }
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(json_payload, jf, indent=2)

    return img_path


def main():
    for b in BILLS_DATA:
        p = render_receipt(b)
        print(f"Generated: {p.name} and {b['id']}.json")

    # Also keep sample_bill.png updated as a copy of bill 1
    import shutil
    shutil.copy(OUTPUT_DIR / "bill_1_indore_spice.png", OUTPUT_DIR / "sample_bill.png")
    shutil.copy(OUTPUT_DIR / "bill_1_indore_spice.json", OUTPUT_DIR / "demo_bill.json")
    print("Completed! 5 realistic sample bills (PNG + JSON) are ready in sample_bills/.")


if __name__ == "__main__":
    main()
