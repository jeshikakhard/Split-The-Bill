"""
calculator.py - ALL financial logic for SplitBill AI.

Design rules (do not violate):
- Every monetary value is a Decimal. Floats never touch money.
- Splitting logic:
    1. Each item's total is split equally among the members assigned to it.
    2. Each person's "gross consumption" = sum of their item shares.
    3. Discount is allocated proportionally to gross consumption.
    4. "Net consumption" = gross consumption - discount share.
    5. Tax and service charge are allocated proportionally to net consumption
       (i.e. after discount, matching how most POS systems apply tax on the
       discounted amount; documented in README).
    6. Final amount = net consumption + tax share + service charge share.
- Rounding: all shares are rounded to 2 decimal places using ROUND_HALF_UP,
  then a largest-remainder reconciliation pass assigns any leftover paisa/
  cents deterministically so the allocated amounts sum EXACTLY to the target.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Dict, List, Sequence

TWO_PLACES = Decimal("0.01")


def q(value: Decimal) -> Decimal:
    """Quantize a Decimal to 2 decimal places (money)."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def split_equally(total: Decimal, n: int) -> List[Decimal]:
    """
    Split `total` equally among `n` shares, each rounded to 2dp, with the
    remainder distributed one cent at a time (deterministic, first shares
    get the extra cent) so the shares sum exactly to `total`.
    """
    if n <= 0:
        return []
    raw_share = total / n
    shares = [q(raw_share) for _ in range(n)]
    residual = q(total) - sum(shares)
    residual_cents = int((residual / TWO_PLACES).to_integral_value(rounding=ROUND_HALF_UP))
    step = TWO_PLACES if residual_cents > 0 else -TWO_PLACES
    for i in range(abs(residual_cents)):
        shares[i % n] += step
    return shares


def allocate_proportional(amount: Decimal, weights: Dict[str, Decimal]) -> Dict[str, Decimal]:
    """
    Allocate `amount` across people according to their `weights` (e.g. each
    person's consumption), proportionally, rounded to 2dp, with a
    largest-remainder reconciliation so shares sum EXACTLY to `amount`.
    """
    names = list(weights.keys())
    amount = q(amount)
    total_weight = sum(weights.values())

    if amount == 0 or total_weight <= 0 or not names:
        return {name: Decimal("0.00") for name in names}

    raw_shares = {name: (amount * weights[name] / total_weight) for name in names}
    rounded = {name: q(raw_shares[name]) for name in names}

    residual = amount - sum(rounded.values())
    residual_cents = int((residual / TWO_PLACES).to_integral_value(rounding=ROUND_HALF_UP))

    if residual_cents != 0:
        # Distribute residual cents to the people with the largest fractional
        # remainder first (largest-remainder method) -- deterministic given
        # a stable sort key (remainder desc, then name asc).
        remainders = sorted(
            names,
            key=lambda n: (-(raw_shares[n] - rounded[n]), n),
        )
        step = TWO_PLACES if residual_cents > 0 else -TWO_PLACES
        for i in range(abs(residual_cents)):
            name = remainders[i % len(remainders)]
            rounded[name] += step

    return rounded


class BillConsistencyWarning(str):
    pass


def check_bill_consistency(
    items_sum: Decimal,
    subtotal: Decimal,
    discount: Decimal,
    tax: Decimal,
    service_charge: Decimal,
    printed_total: Decimal | None,
    tolerance: Decimal = Decimal("1.00"),
) -> List[str]:
    """Return a list of human-readable warnings about internal bill math."""
    warnings: List[str] = []

    if abs(items_sum - subtotal) > tolerance:
        warnings.append(
            f"Line items sum to {items_sum} but subtotal is listed as {subtotal} "
            f"(difference {abs(items_sum - subtotal)})."
        )

    computed_total = subtotal - discount + tax + service_charge
    if printed_total is not None and abs(computed_total - printed_total) > tolerance:
        warnings.append(
            "The printed bill total does not match the extracted components "
            f"(subtotal - discount + tax + service = {computed_total}, "
            f"printed total = {printed_total}, difference = "
            f"{abs(computed_total - printed_total)})."
        )

    return warnings


def compute_split(
    item_totals: Sequence[Decimal],
    item_names: Sequence[str],
    assignments: Sequence[Sequence[str]],
    members: Sequence[str],
    discount: Decimal,
    tax: Decimal,
    service_charge: Decimal,
    printed_total: Decimal | None,
) -> dict:
    """
    Compute the full per-person breakdown.

    item_totals, item_names, assignments are parallel sequences (one entry
    per bill item). assignments[i] is the list of member names sharing item i.

    Returns a plain dict (JSON-friendly) with per-person breakdowns, totals,
    reconciliation info and warnings. Kept provider/UI agnostic on purpose.
    """
    assert len(item_totals) == len(item_names) == len(assignments)

    person_items: Dict[str, List[dict]] = {m: [] for m in members}
    gross_consumption: Dict[str, Decimal] = {m: Decimal("0.00") for m in members}

    for name, total, assigned_to in zip(item_names, item_totals, assignments):
        valid_assignees = [m for m in assigned_to if m in person_items]
        if not valid_assignees:
            continue
        shares = split_equally(q(total), len(valid_assignees))
        for member, share in zip(valid_assignees, shares):
            gross_consumption[member] += share
            person_items[member].append(
                {
                    "name": name,
                    "share": str(share),
                    "is_shared": len(valid_assignees) > 1,
                    "shared_with": [x for x in valid_assignees if x != member],
                }
            )

    items_sum = q(sum(item_totals, Decimal("0")))
    subtotal = q(sum(gross_consumption.values(), Decimal("0")))

    # Step 1: discount allocated proportionally to gross consumption.
    discount_shares = allocate_proportional(discount, gross_consumption)

    net_consumption = {
        m: gross_consumption[m] - discount_shares.get(m, Decimal("0.00")) for m in members
    }

    # Step 2: tax & service charge allocated proportionally to NET consumption.
    tax_shares = allocate_proportional(tax, net_consumption)
    service_shares = allocate_proportional(service_charge, net_consumption)

    people = []
    allocated_total = Decimal("0.00")
    for m in members:
        final_amount = q(
            net_consumption[m] + tax_shares.get(m, Decimal("0.00")) + service_shares.get(m, Decimal("0.00"))
        )
        allocated_total += final_amount
        people.append(
            {
                "name": m,
                "items": person_items[m],
                "gross_consumption": str(gross_consumption[m]),
                "discount_share": str(discount_shares.get(m, Decimal("0.00"))),
                "net_consumption": str(net_consumption[m]),
                "tax_share": str(tax_shares.get(m, Decimal("0.00"))),
                "service_charge_share": str(service_shares.get(m, Decimal("0.00"))),
                "final_amount": str(final_amount),
            }
        )

    allocated_total = q(allocated_total)
    bill_total = q(printed_total) if printed_total is not None else q(
        subtotal - discount + tax + service_charge
    )
    difference = q(bill_total - allocated_total)

    warnings = check_bill_consistency(
        items_sum=items_sum,
        subtotal=subtotal,
        discount=discount,
        tax=tax,
        service_charge=service_charge,
        printed_total=printed_total,
    )

    printed_total_available = printed_total is not None
    if not printed_total_available:
        warnings.append(
            "Printed total was not available (left blank/unreadable) - the "
            "'bill total' shown is computed from subtotal, discount, tax and "
            "service charge instead of the number actually printed on the bill."
        )

    return {
        "people": people,
        "bill_total": str(bill_total),
        "printed_total_available": printed_total_available,
        "allocated_total": str(allocated_total),
        "difference": str(difference),
        "is_reconciled": abs(difference) <= Decimal("0.01"),
        "warnings": warnings,
    }
