"""Repair playbook lookup for the operator dashboard.

Repair guidance isn't stored as a column, so we derive it: first by the
machine-readable `defect_code` on the detection payload, then fall back to a
station-level default, then a generic catch-all. Each entry yields the fields
the operator dashboard renders: a one-line summary, an ordered checklist of
steps, the tools required, and a recommended disposition.
"""

# Keyed by detection payload `defect_code`.
_BY_CODE = {
    "SURF_SCRATCH": {
        "summary": "Surface scratch beyond cosmetic tolerance.",
        "tools": ["Polishing pad", "Grit-2000 paper", "Calipers"],
        "steps": [
            "Lock out the conveyor segment at this station before reaching in.",
            "Lift the part and confirm the scratch location against the QC image.",
            "Wet-sand the affected face with grit-2000, then buff with the polishing pad.",
            "Re-measure depth with calipers — must be under 2.0mm.",
            "If still out of tolerance, tag the part SCRAP and drop it in the reject bin.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Rework in place; scrap if depth > 2.0mm.",
        "est_minutes": 4,
    },
    "MISALIGN": {
        "summary": "Component misaligned past the assembly tolerance.",
        "tools": ["2.5mm hex driver", "Alignment jig", "Feeler gauge"],
        "steps": [
            "Lock out the conveyor segment at this station.",
            "Seat the part in the alignment jig.",
            "Loosen the bracket screws with the 2.5mm hex driver.",
            "Slide the bracket until the feeler gauge reads under 0.5mm offset.",
            "Re-torque the screws to 0.6 N·m in a diagonal pattern.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Rework in place; re-run QC after fix.",
        "est_minutes": 6,
    },
}

# Fallback keyed by station name.
_BY_STATION = {
    "intake": {
        "summary": "Part flagged at intake before inspection.",
        "tools": ["Barcode scanner", "Intake checklist"],
        "steps": [
            "Confirm the part label and SKU against the work order.",
            "Re-scan the barcode; if unreadable, apply a fresh label.",
            "Return the part to the line head or divert to manual review.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Re-induct or divert to manual review.",
        "est_minutes": 3,
    },
    "inspection": {
        "summary": "Defect detected during automated inspection.",
        "tools": ["Inspection loupe", "Calipers"],
        "steps": [
            "Lock out the conveyor segment at this station.",
            "Compare the part to the QC image to locate the defect.",
            "Apply the standard rework for the defect class, or scrap if irreparable.",
            "Re-run inspection after the fix.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Rework and re-inspect.",
        "est_minutes": 5,
    },
    "qc_gate": {
        "summary": "Part held at the QC gate pending operator decision.",
        "tools": ["QC checklist", "Calipers"],
        "steps": [
            "Lock out the conveyor segment at this station.",
            "Review the held part against the QC acceptance criteria.",
            "Pass it downstream, return it for rework, or reject it.",
            "Record the go/no-go decision and mark complete on this screen.",
        ],
        "disposition": "Operator go/no-go decision required.",
        "est_minutes": 3,
    },
    "packaging": {
        "summary": "Defect caught at packaging.",
        "tools": ["Packaging kit", "Label printer"],
        "steps": [
            "Pull the part from the packaging queue.",
            "Inspect packaging integrity and the part itself.",
            "Repackage or divert to rework as needed.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Repackage or divert to rework.",
        "est_minutes": 4,
    },
}

_GENERIC = {
    "summary": "Part flagged as faulty — manual review required.",
    "tools": ["Standard rework kit"],
    "steps": [
        "Lock out the conveyor segment at this station before reaching in.",
        "Inspect the part and locate the fault.",
        "Apply the appropriate rework, or scrap if irreparable.",
        "Mark the repair complete on this screen to clear the alert.",
    ],
    "disposition": "Manual review.",
    "est_minutes": 5,
}


def lookup(defect_code: str | None, station_name: str | None) -> dict:
    """Return the best-matching repair entry for a defect."""
    if defect_code and defect_code in _BY_CODE:
        return _BY_CODE[defect_code]
    if station_name and station_name in _BY_STATION:
        return _BY_STATION[station_name]
    return _GENERIC
