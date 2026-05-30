"""
Business logic rules that transform raw vision + robot state into calculated states.
Used by both upstream_sync (for DB writes) and main.py (for live debug overlay).
"""


def _force(result: dict, pos: int, present: bool):
    result[f"pos{pos}_item_present"] = present
    if not present:
        result[f"pos{pos}_item_status"] = ""


def apply_rules(vision: dict, robot: dict) -> dict:
    """
    vision: {pos1_item_present, pos1_item_status, ...}
    robot:  {curr_pos, pose, ...}

    Rules:
      robot at 4: holding → pos4=False, not holding → trust vision
      robot at 3: pos4 always False; holding → pos3=False, not holding → trust vision
      robot at 5: pos3+pos4 always False; holding → pos5=False, not holding → trust vision
      elsewhere:  trust vision
    """
    result   = dict(vision)
    pose     = robot.get("pose", "")
    curr_pos = robot.get("curr_pos")
    holding  = "part_true" in pose

    if curr_pos == 4:
        if holding:
            _force(result, 4, False)

    elif curr_pos == 3:
        _force(result, 4, False)
        if holding:
            _force(result, 3, False)

    elif curr_pos == 5:
        _force(result, 3, False)
        _force(result, 4, False)
        if holding:
            _force(result, 5, False)

    return result
