"""Repair playbook lookup for the operator dashboard.

Repair guidance isn't stored as a column, so we derive it: first by the fault
text the vision service records on `faulty_parts.fault` (lowercased), then fall
back to a station-level default, then a generic catch-all. Each entry yields the
fields the operator dashboard renders: a one-line summary, an ordered checklist
of steps, the tools required, and a recommended disposition.
"""

# Keyed by the lowercased `faulty_parts.fault` text.
_BY_CODE = {
    "surface damage": {
        "summary": "Surface anomaly — part is not conforming (non-white in the QC view).",
        "tools": ["Polishing pad", "Grit-2000 paper", "Inspection loupe"],
        "steps": [
            "Lock out the conveyor segment at this station before reaching in.",
            "Lift the part and confirm the damage against the camera capture.",
            "Wet-sand and buff the affected face, or wipe down if it's surface debris.",
            "Re-inspect under the loupe; the face should read uniformly clean/white.",
            "If the damage can't be reworked, tag the part SCRAP and drop it in the reject bin.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Rework in place; scrap if it can't be cleaned up.",
        "est_minutes": 4,
    },
    "bad paint": {
        "summary": "Paint defect — coating is off-spec (runs, thin coverage, or wrong shade).",
        "tools": ["Sanding block", "Touch-up paint", "Tack cloth"],
        "steps": [
            "Lock out the conveyor segment at this station.",
            "Compare the finish to the reference against the camera capture.",
            "Scuff the affected area and wipe with the tack cloth.",
            "Apply a thin touch-up coat; let it flash before re-stacking.",
            "If coverage is badly off, divert the part to the repaint queue.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Touch up in place; divert to repaint if severe.",
        "est_minutes": 5,
    },
    "label misaligned": {
        "summary": "Label is skewed or off-position past tolerance.",
        "tools": ["Label scraper", "Spare labels", "Alignment guide"],
        "steps": [
            "Lock out the conveyor segment at this station.",
            "Peel the misapplied label with the scraper.",
            "Clean any adhesive residue from the surface.",
            "Apply a fresh label using the alignment guide.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Re-label in place.",
        "est_minutes": 3,
    },
    "packaging broken": {
        "summary": "Packaging is damaged or open.",
        "tools": ["Replacement packaging", "Tape gun"],
        "steps": [
            "Pull the part from the packaging queue.",
            "Inspect the part inside for damage from the broken packaging.",
            "If the part is intact, repackage it; otherwise divert to rework.",
            "Reseal and return to the line.",
            "Mark the repair complete on this screen to clear the alert.",
        ],
        "disposition": "Repackage; divert part to rework if damaged.",
        "est_minutes": 4,
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
