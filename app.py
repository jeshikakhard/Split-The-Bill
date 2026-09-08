"""
app.py - SplitBill AI Streamlit interface.

Four-step deterministic workflow:
  1. Upload  - Upload a bill photo, test sample receipt, or load demo bill
  2. Review  - Human reviews and edits every AI-extracted field (add/delete items)
  3. Assign  - Add 2-3 members and define who ate what (single, shared, all)
  4. Results - Reconciled per-person breakdown with proportional tax/service/discount

NO CHATBOT: Pure vision perception + Pydantic validation + Decimal calculation.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
import os
import streamlit as st

from calculator import compute_split
from extractor import (
    ExtractionError,
    SAMPLE_BILLS,
    extract_bill_from_image,
    get_api_key,
    load_demo_bill,
    load_sample_bill,
)
from models import Bill, BillItem
from utils import (
    all_items_assigned,
    confidence_badge,
    format_money,
    safe_decimal,
    validate_member_names,
)

STEPS = ["Upload", "Review", "Assign", "Results"]
SAMPLE_BILL_IMG = Path(__file__).parent / "sample_bills" / "sample_bill.png"

st.set_page_config(
    page_title="SplitBill AI — Fair Restaurant Bill Splitter",
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS for modern, high-polish aesthetics
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
}

/* Main title styling */
.main-title {
    font-size: 2.2rem;
    font-weight: 800;
    letter-spacing: -0.02em;
    margin-bottom: 2px;
    display: flex;
    align-items: center;
    gap: 10px;
}

.sub-title {
    font-size: 1.05rem;
    color: #64748b;
    margin-bottom: 20px;
}

/* Header badge */
.badge-no-chat {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: linear-gradient(135deg, #2563eb, #7c3aed);
    color: #ffffff !important;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 4px 12px;
    border-radius: 20px;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
    margin-bottom: 8px;
}

/* Stepper styles */
.stepper-wrap {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: rgba(148, 163, 184, 0.08);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 10px 16px;
    margin-bottom: 24px;
}

.step-node {
    display: flex;
    align-items: center;
    gap: 8px;
    font-weight: 600;
    font-size: 0.90rem;
    color: #94a3b8;
    padding: 6px 12px;
    border-radius: 8px;
}

.step-node.active {
    color: #0284c7;
    background: rgba(2, 132, 199, 0.12);
    font-weight: 700;
    border: 1px solid rgba(2, 132, 199, 0.25);
}

.step-node.completed {
    color: #10b981;
}

/* Container polish */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 12px !important;
    border: 1px solid rgba(148, 163, 184, 0.22) !important;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}

/* Metric styling */
[data-testid="stMetricValue"] {
    font-weight: 800 !important;
    font-size: 1.65rem !important;
}

/* Button style accents */
button[kind="primary"] {
    font-weight: 600 !important;
    border-radius: 8px !important;
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Session state helpers
# ---------------------------------------------------------------------------

def init_state():
    defaults = {
        "step": 1,
        "bill": None,
        "extraction_error": None,
        "members": ["", "", ""],
        "assignments": {},
        "result": None,
        "custom_api_key": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def go_to(step: int):
    st.session_state.step = step


def clear_bill_scoped_widget_state():
    """Remove per-item / per-assignment widget keys to prevent stale widget state."""
    prefixes = ("item_name_", "item_qty_", "item_unit_", "item_total_", "assign_")
    for key in list(st.session_state.keys()):
        if key.startswith(prefixes):
            del st.session_state[key]


def render_stepper():
    cols = st.columns(len(STEPS))
    for i, (col, label) in enumerate(zip(cols, STEPS), start=1):
        with col:
            if i < st.session_state.step:
                st.markdown(f"**✅ {i}. {label}**")
            elif i == st.session_state.step:
                st.markdown(f"**🔷 {i}. {label}** *(Current)*")
            else:
                st.markdown(f"⚪ {i}. {label}")
    st.divider()


def render_sidebar():
    with st.sidebar:
        st.markdown("### 🧾 SplitBill AI")
        st.markdown(
            "Turn any restaurant bill photograph into an **accurate, itemized split** "
            "between 2–3 people with **proportional tax & service charge**."
        )

        st.divider()
        st.markdown("#### ⚙️ Architecture")
        st.caption(
            "1. **AI Perception**: Vision extraction\n"
            "2. **Pydantic**: Schema validation\n"
            "3. **Human Review**: Verification & edits\n"
            "4. **Python Decimal**: 100% deterministic math"
        )
        st.markdown("🚫 **Zero Chatbots** — Form-driven accuracy.")

        st.divider()
        st.markdown("#### 🔑 Gemini API Key")
        env_key = get_api_key()
        if env_key:
            st.success("API Key detected from `.env` or system.")
        else:
            st.info("No API Key detected. Using **Demo Mode** or enter key below:")
            custom_key = st.text_input(
                "Optional API Key for this session:",
                type="password",
                value=st.session_state.custom_api_key,
                key="input_custom_api_key",
            )
            if custom_key:
                st.session_state.custom_api_key = custom_key.strip()
                os.environ["GEMINI_API_KEY"] = custom_key.strip()

        st.divider()
        st.markdown("#### 📁 5 Example Receipts (PNG)")
        st.caption("Download receipt images to test the file uploader:")
        for bid, binfo in SAMPLE_BILLS.items():
            if binfo["img_path"].exists():
                with open(binfo["img_path"], "rb") as f:
                    idata = f.read()
                st.download_button(
                    label=f"📥 {binfo['title'].split('(')[0].strip()}",
                    data=idata,
                    file_name=f"{bid}.png",
                    mime="image/png",
                    key=f"dl_side_{bid}",
                    use_container_width=True,
                )

        st.divider()
        if st.button("🔄 Reset Entire App", use_container_width=True):
            clear_bill_scoped_widget_state()
            for key in ["bill", "extraction_error", "members", "assignments", "result"]:
                if key in st.session_state:
                    del st.session_state[key]
            init_state()
            st.rerun()


# ---------------------------------------------------------------------------
# Step 1: Upload
# ---------------------------------------------------------------------------

def render_upload():
    st.subheader("Step 1 · Upload Bill Photograph")
    st.write(
        "Upload a photograph of your restaurant bill. SplitBill AI extracts the printed items, "
        "quantities, and taxes into structured data with confidence indicators. "
        "You will review and verify every field before any money calculations occur."
    )

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded = st.file_uploader(
            "Upload restaurant bill image",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=False,
            help="Take or upload a legible photo of the restaurant bill receipt.",
        )

        if uploaded is not None:
            st.image(uploaded, caption="Uploaded Bill Image", use_container_width=True)
            if st.button("🔍 Extract Bill with AI", type="primary", use_container_width=True):
                with st.spinner("Extracting structured bill data with Gemini Vision..."):
                    try:
                        mime = uploaded.type or "image/jpeg"
                        bill = extract_bill_from_image(uploaded.getvalue(), mime_type=mime)
                        clear_bill_scoped_widget_state()
                        st.session_state.bill = bill
                        st.session_state.assignments = {}
                        st.session_state.extraction_error = None
                        go_to(2)
                        st.rerun()
                    except ExtractionError as e:
                        st.session_state.extraction_error = str(e)

        if st.session_state.extraction_error:
            st.error(f"⚠️ {st.session_state.extraction_error}")
            st.info("💡 You can select any of our **5 Example Bills** on the right to test SplitBill AI immediately without an API key.")

    with col2:
        with st.container(border=True):
            st.markdown("#### 🎬 5 Pre-loaded Example Bills")
            st.write(
                "Don't have a real bill photo? Choose from **5 realistic restaurant receipts** "
                "with pre-configured items, taxes, discounts, and member assignments:"
            )

            sample_options = {
                "bill_1_indore_spice": "🍲 1. Indore Spice Kitchen (Biryani, Pizza — ₹1,357)",
                "bill_2_urban_cafe": "☕ 2. Urban Brew Cafe (Brunch, Coffee — ₹1,311)",
                "bill_3_bella_italia": "🍕 3. Bella Italia (Pizza, Pasta, 10% Off — ₹1,749)",
                "bill_4_south_indian": "🥞 4. Dakshin Tiffin Room (Dosas, Coffee — ₹672)",
                "bill_5_burger_co": "🍔 5. Smash Burger Co. (Burgers, Shakes — ₹1,716)",
            }

            chosen_id = st.selectbox(
                "Select Example Bill:",
                options=list(sample_options.keys()),
                format_func=lambda x: sample_options[x],
                key="chosen_sample_bill_select",
            )

            chosen_info = SAMPLE_BILLS[chosen_id]

            # Direct 1-click load into workflow
            if st.button("▶️ Load Selected Bill into Workflow", type="primary", use_container_width=True):
                clear_bill_scoped_widget_state()
                loaded_bill = load_sample_bill(chosen_id)
                st.session_state.bill = loaded_bill
                st.session_state.members = list(chosen_info["default_members"])
                st.session_state.assignments = dict(chosen_info["default_assignments"])
                st.session_state.extraction_error = None
                go_to(2)
                st.rerun()

            st.caption("✅ Loads structured bill data directly into Step 2 (Review) without an API key.")

            # Expandable receipt viewer & downloader
            with st.expander("🖼️ View & Download Receipt Image", expanded=False):
                if chosen_info["img_path"].exists():
                    st.image(str(chosen_info["img_path"]), caption=chosen_info["title"], use_container_width=True)
                    with open(chosen_info["img_path"], "rb") as f:
                        img_bytes = f.read()
                    st.download_button(
                        label=f"📥 Download '{chosen_id}.png'",
                        data=img_bytes,
                        file_name=f"{chosen_id}.png",
                        mime="image/png",
                        key=f"dl_preview_{chosen_id}",
                        use_container_width=True,
                    )
                    # Option to run live AI extraction on this sample image if key is set
                    if st.button(f"🔍 Extract '{chosen_id}' with Gemini AI", key=f"ai_btn_{chosen_id}", use_container_width=True):
                        with st.spinner("Extracting with Gemini Vision..."):
                            try:
                                bill = extract_bill_from_image(img_bytes, mime_type="image/png")
                                clear_bill_scoped_widget_state()
                                st.session_state.bill = bill
                                st.session_state.members = list(chosen_info["default_members"])
                                st.session_state.assignments = {}
                                st.session_state.extraction_error = None
                                go_to(2)
                                st.rerun()
                            except ExtractionError as e:
                                st.session_state.extraction_error = str(e)


# ---------------------------------------------------------------------------
# Step 2: Review
# ---------------------------------------------------------------------------

def render_review():
    bill: Bill = st.session_state.bill
    st.subheader("Step 2 · Human Review & Verification")

    if bill.is_demo:
        st.info("🎬 **Demo bill — sample data.** Not extracted from a live image. All values are editable.")
    else:
        st.success("🔍 **AI Extraction Complete.** Please verify and correct any field below before proceeding.")

    st.caption(
        "Confidence Badges: 🟢 **High** (≥90%) · 🟡 **Medium** (70–89%) · 🔴 **Review** (<70%). "
        "These indicate visual extraction clarity, not mathematical probabilities."
    )

    # Restaurant Name & Date
    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("Restaurant Name", value=bill.restaurant_name or "")
        st.caption(f"Extraction Confidence: {confidence_badge(bill.field_confidence.restaurant_name)}")
    with c2:
        date = st.text_input("Date", value=bill.date or "")
        st.caption(f"Extraction Confidence: {confidence_badge(bill.field_confidence.date)}")

    st.markdown("#### 🍽️ Line Items")
    st.caption("Check each item's name, quantity, unit price, and total. Add or remove items if needed.")

    edited_items: list[BillItem] = []
    indices_to_delete = []

    for idx, item in enumerate(bill.items):
        with st.container(border=True):
            cols = st.columns([3, 1, 1.2, 1.4, 1.4, 0.5])
            item_name = cols[0].text_input(f"Item #{idx+1} Name", value=item.name, key=f"item_name_{idx}")
            qty = cols[1].text_input("Qty", value=str(item.quantity), key=f"item_qty_{idx}")
            unit_price = cols[2].text_input(
                "Unit Price (₹)",
                value=str(item.unit_price) if item.unit_price is not None else "",
                key=f"item_unit_{idx}",
            )
            total = cols[3].text_input("Item Total (₹)", value=str(item.total), key=f"item_total_{idx}")
            cols[4].markdown(f"<div style='margin-top:28px'>{confidence_badge(item.confidence)}</div>", unsafe_allow_html=True)
            
            # Delete button (only allow if > 1 item exists)
            if len(bill.items) > 1:
                if cols[5].button("🗑️", key=f"del_item_{idx}", help="Delete this item"):
                    indices_to_delete.append(idx)

            parsed_total = safe_decimal(total, Decimal("0.00"))
            edited_items.append(
                BillItem(
                    name=item_name.strip() or item.name,
                    quantity=safe_decimal(qty, Decimal("1")),
                    unit_price=safe_decimal(unit_price, None),
                    total=parsed_total,
                    confidence=item.confidence,
                )
            )

    # Handle deletion if triggered
    if indices_to_delete:
        for idx in sorted(indices_to_delete, reverse=True):
            bill.items.pop(idx)
        clear_bill_scoped_widget_state()
        st.rerun()

    # Add Item Button
    if st.button("➕ Add Line Item", type="secondary"):
        bill.items.append(
            BillItem(
                name=f"Custom Item {len(bill.items) + 1}",
                quantity=Decimal("1"),
                unit_price=Decimal("0.00"),
                total=Decimal("0.00"),
                confidence=1.0,
            )
        )
        clear_bill_scoped_widget_state()
        st.rerun()

    st.markdown("#### 💰 Bill Totals & Taxes")
    t1, t2, t3, t4, t5 = st.columns(5)
    with t1:
        subtotal = t1.text_input(
            "Subtotal (₹)", value=str(bill.subtotal) if bill.subtotal is not None else ""
        )
        t1.caption(f"Subtotal: {confidence_badge(bill.field_confidence.subtotal)}")
    with t2:
        discount = t2.text_input("Discount (₹)", value=str(bill.discount or "0"))
        t2.caption(f"Discount: {confidence_badge(bill.field_confidence.discount)}")
    with t3:
        tax = t3.text_input("GST / Tax (₹)", value=str(bill.tax or "0"))
        t3.caption(f"GST: {confidence_badge(bill.field_confidence.tax)}")
    with t4:
        service_charge = t4.text_input("Service Charge (₹)", value=str(bill.service_charge or "0"))
        t4.caption(f"Service: {confidence_badge(bill.field_confidence.service_charge)}")
    with t5:
        total_val = t5.text_input(
            "Printed Total (₹)", value=str(bill.total) if bill.total is not None else ""
        )
        t5.caption(f"Total: {confidence_badge(bill.field_confidence.total)}")

    # Consistency checks
    items_sum = sum((i.total for i in edited_items), Decimal("0"))
    subtotal_val = safe_decimal(subtotal, items_sum)
    discount_val = safe_decimal(discount, Decimal("0.00"))
    tax_val = safe_decimal(tax, Decimal("0.00"))
    service_val = safe_decimal(service_charge, Decimal("0.00"))
    printed_val = safe_decimal(total_val, None)

    computed_sum = subtotal_val - discount_val + tax_val + service_val

    if abs(items_sum - subtotal_val) > Decimal("1.00"):
        st.warning(
            f"⚠️ **Line Items Mismatch**: Items sum to **{format_money(items_sum)}** "
            f"but subtotal is listed as **{format_money(subtotal_val)}** (diff: {format_money(abs(items_sum - subtotal_val))}). "
            f"You can adjust either above."
        )

    if printed_val is not None and abs(computed_sum - printed_val) > Decimal("1.00"):
        st.warning(
            f"⚠️ **Printed Total Inconsistency**: Subtotal - Discount + Tax + Service = "
            f"**{format_money(computed_sum)}**, but printed total is **{format_money(printed_val)}** "
            f"(diff: {format_money(abs(computed_sum - printed_val))})."
        )

    st.divider()
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("⬅️ Back to Upload", use_container_width=True):
            go_to(1)
            st.rerun()
    with b2:
        if st.button("✅ Confirm Bill & Proceed to Assign ➡️", type="primary", use_container_width=True):
            confirmed = Bill(
                restaurant_name=name.strip() or None,
                date=date.strip() or None,
                items=edited_items,
                subtotal=subtotal_val,
                discount=discount_val,
                tax=tax_val,
                service_charge=service_val,
                total=printed_val,
                field_confidence=bill.field_confidence.model_dump() if hasattr(bill.field_confidence, "model_dump") else bill.field_confidence,
                is_demo=bill.is_demo,
                raw_notes=bill.raw_notes,
            )
            st.session_state.bill = confirmed
            go_to(3)
            st.rerun()


# ---------------------------------------------------------------------------
# Step 3: Assign
# ---------------------------------------------------------------------------

def render_assign():
    bill: Bill = st.session_state.bill
    st.subheader("Step 3 · Add Members & Assign Items")

    st.markdown("#### 👥 Group Members (Exact 2–3 People)")
    st.caption("Specify 2 or 3 distinct member names who are splitting this bill.")

    cols = st.columns(3)
    members_input = list(st.session_state.members)
    for i in range(3):
        members_input[i] = cols[i].text_input(
            f"Member {i + 1}" + (" (optional)" if i == 2 else ""),
            value=members_input[i],
            key=f"member_input_{i}",
            placeholder=f"e.g. {['Jeshika', 'Rahul', 'Priya'][i]}",
        )
    st.session_state.members = members_input

    valid, err = validate_member_names(members_input)
    member_names = [n.strip() for n in members_input if n and n.strip()]

    if not valid:
        st.warning(f"⚠️ {err}")
        st.divider()
        b1, _ = st.columns([1, 1])
        with b1:
            if st.button("⬅️ Back to Review", use_container_width=True):
                go_to(2)
                st.rerun()
        return

    st.markdown("#### 🍽️ Who Ate What?")
    st.caption("For each item, select who consumed it. Shared items split equally. Every item requires ≥1 person.")

    # Guard: prune stale members from assignment state
    for idx in range(len(bill.items)):
        wkey = f"assign_{idx}"
        if wkey in st.session_state:
            st.session_state[wkey] = [m for m in st.session_state[wkey] if m in member_names]
        elif idx in st.session_state.assignments:
            st.session_state[wkey] = [m for m in st.session_state.assignments[idx] if m in member_names]

    assignments = {}

    for idx, item in enumerate(bill.items):
        with st.container(border=True):
            c1, c2, c3 = st.columns([2, 3, 1])
            c1.markdown(f"**{item.name}** (x{item.quantity})<br><span style='color:#0284c7;font-weight:700;'>{format_money(item.total)}</span>", unsafe_allow_html=True)
            
            wkey = f"assign_{idx}"
            if wkey not in st.session_state:
                st.session_state[wkey] = [m for m in st.session_state.assignments.get(idx, []) if m in member_names]

            selected = c2.multiselect(
                f"Assignees for {item.name}",
                options=member_names,
                key=wkey,
                label_visibility="collapsed",
            )
            assignments[idx] = selected

            # Quick "Everyone" button
            if c3.button("👥 All", key=f"all_btn_{idx}", help="Assign this item to everyone"):
                st.session_state[wkey] = list(member_names)
                assignments[idx] = list(member_names)
                st.rerun()

    st.session_state.assignments = assignments
    ok, missing = all_items_assigned(assignments, len(bill.items))

    st.divider()
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("⬅️ Back to Review", use_container_width=True):
            go_to(2)
            st.rerun()
    with b2:
        if not ok:
            missing_names = ", ".join(f"'{bill.items[i].name}'" for i in missing)
            st.error(f"⚠️ Unassigned item(s): {missing_names}. Please assign at least one person.")
        
        if st.button("🧮 Calculate Split ➡️", type="primary", disabled=not ok, use_container_width=True):
            result = compute_split(
                item_totals=[i.total for i in bill.items],
                item_names=[i.name for i in bill.items],
                assignments=[assignments[i] for i in range(len(bill.items))],
                members=member_names,
                discount=bill.discount,
                tax=bill.tax,
                service_charge=bill.service_charge,
                printed_total=bill.total,
            )
            st.session_state.result = result
            go_to(4)
            st.rerun()


# ---------------------------------------------------------------------------
# Step 4: Results
# ---------------------------------------------------------------------------

def render_results():
    bill: Bill = st.session_state.bill
    result = st.session_state.result
    st.subheader("Step 4 · Itemized Breakdown & Reconciliation")

    if result["warnings"]:
        for w in result["warnings"]:
            st.warning(f"⚠️ {w}")

    # Top metrics row
    m1, m2, m3 = st.columns(3)
    total_label = (
        "Printed Bill Total" if result["printed_total_available"] else "Bill Total (Computed)"
    )
    m1.metric(total_label, format_money(Decimal(result["bill_total"])))
    m2.metric("Allocated Total", format_money(Decimal(result["allocated_total"])))
    diff = Decimal(result["difference"])
    m3.metric("Reconciliation Difference", format_money(diff), delta=f"{diff:+.2f}")

    if result["is_reconciled"]:
        st.success("✅ **Perfect Reconciliation**: Sum of individual member shares exactly equals the bill total.")
    else:
        st.error(
            f"❌ **Unreconciled Variance**: Difference of {format_money(diff)}. "
            "The printed bill total does not match the sum of items + taxes - discount."
        )

    st.divider()

    # Summary table across all members
    st.markdown("#### 📊 Group Split Summary")
    table_rows = []
    for p in result["people"]:
        table_rows.append(
            {
                "Member": p["name"],
                "Consumption (Gross)": format_money(Decimal(p["gross_consumption"])),
                "Discount Share": f"-{format_money(Decimal(p['discount_share']))}" if Decimal(p["discount_share"]) > 0 else "₹0.00",
                "Net Consumption": format_money(Decimal(p["net_consumption"])),
                "GST / Tax Share": format_money(Decimal(p["tax_share"])),
                "Service Charge Share": format_money(Decimal(p["service_charge_share"])),
                "Final Amount Owed": format_money(Decimal(p["final_amount"])),
            }
        )
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### 👤 Detailed Individual Breakdowns")

    for person in result["people"]:
        with st.expander(
            f"**{person['name']}** — Total: **{format_money(Decimal(person['final_amount']))}**",
            expanded=True,
        ):
            if person["items"]:
                st.markdown("**Items Consumed:**")
                for it in person["items"]:
                    shared_info = f" *(shared with {', '.join(it['shared_with'])})*" if it["is_shared"] else " *(individual)*"
                    st.write(f"• **{it['name']}**: {format_money(Decimal(it['share']))}{shared_info}")
            else:
                st.caption("No items assigned.")

            st.markdown("---")
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Gross Food", format_money(Decimal(person["gross_consumption"])))
            disc_amt = Decimal(person["discount_share"])
            c2.metric("Discount", f"-{format_money(disc_amt)}" if disc_amt > 0 else "₹0.00")
            c3.metric("GST Share", format_money(Decimal(person["tax_share"])))
            c4.metric("Service Share", format_money(Decimal(person["service_charge_share"])))
            c5.metric("Final Total", format_money(Decimal(person["final_amount"])))

    st.caption(
        "ℹ️ **Calculation Policy**: GST and Service Charge are allocated proportionally based on each person's "
        "net consumption (after proportional discount). Fractional cents are reconciled deterministically via largest-remainder method."
    )

    st.divider()
    b1, b2 = st.columns([1, 1])
    with b1:
        if st.button("⬅️ Back to Assign", use_container_width=True):
            go_to(3)
            st.rerun()
    with b2:
        if st.button("🔄 Start New Bill", type="primary", use_container_width=True):
            clear_bill_scoped_widget_state()
            for key in ["bill", "extraction_error", "members", "assignments", "result"]:
                if key in st.session_state:
                    del st.session_state[key]
            go_to(1)
            st.rerun()


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

def main():
    init_state()
    render_sidebar()

    st.markdown('<div class="badge-no-chat">⚡ Deterministic Math · Zero Chatbots · Pydantic Validated</div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title">🧾 SplitBill AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Turn a restaurant bill photo into a fair, itemized split between 2–3 people.</div>', unsafe_allow_html=True)

    render_stepper()

    step = st.session_state.step
    if step == 1 or st.session_state.bill is None:
        render_upload()
    elif step == 2:
        render_review()
    elif step == 3:
        render_assign()
    elif step == 4:
        render_results()


if __name__ == "__main__":
    main()
