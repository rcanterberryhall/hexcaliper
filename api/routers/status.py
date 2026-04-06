"""
routers/status.py — Cross-service status summary endpoints.

Used by the merLLM 'My Day' panel to get a count of items needing attention
without requiring a full dashboard load.
"""
from fastapi import APIRouter

import db

router = APIRouter()


@router.get("/status/pending")
def pending_status():
    """
    Return counts of items awaiting review in LanceLLMot.

    :return: Dict with acquisition and escalation pending counts.
    :rtype: dict
    """
    acquisition_pending = db.list_acquisition_queue(status="pending_approval")
    escalation_pending  = db.list_escalation_queue(status="pending_approval")
    return {
        "acquisition_pending": len(acquisition_pending),
        "escalation_pending":  len(escalation_pending),
        "total_pending":       len(acquisition_pending) + len(escalation_pending),
    }
