"""
End-to-end integration test validating the complete calculation pipeline
for all 5 bundled sample bills without browser or UI dependencies.
"""

from decimal import Decimal
import pytest

from extractor import SAMPLE_BILLS, load_sample_bill
from calculator import compute_split


@pytest.mark.parametrize("bill_id", list(SAMPLE_BILLS.keys()))
def test_end_to_end_pipeline_for_each_sample_bill(bill_id):
    info = SAMPLE_BILLS[bill_id]
    bill = load_sample_bill(bill_id)
    
    # Verify bill model fields
    assert bill.is_demo is True
    assert len(bill.items) >= 3
    assert bill.subtotal > Decimal("0")
    
    members = info["default_members"]
    assignments = [info["default_assignments"][i] for i in range(len(bill.items))]
    
    # Run the calculator engine
    result = compute_split(
        item_totals=[i.total for i in bill.items],
        item_names=[i.name for i in bill.items],
        assignments=assignments,
        members=members,
        discount=bill.discount,
        tax=bill.tax,
        service_charge=bill.service_charge,
        printed_total=bill.total,
    )
    
    # Assertions on calculation results
    assert result["is_reconciled"] is True, f"Reconciliation failed for {bill_id}: diff={result['difference']}"
    assert Decimal(result["difference"]) == Decimal("0.00")
    assert Decimal(result["allocated_total"]) == Decimal(result["bill_total"])
    assert len(result["people"]) == len(members)
    
    # Verify sum of individuals equals allocated total
    sum_individuals = sum(Decimal(p["final_amount"]) for p in result["people"])
    assert sum_individuals == Decimal(result["allocated_total"])
