"""
state.py — Urush va a'zolar holatini saqlash
"""

import logging

log = logging.getLogger(__name__)

# ── War state ─────────────────────────────────────────────────────────────────
war: dict = {
    "war_id":                 None,   # preparationStartTime — unique per war
    "preparation_announced":  False,
    "war_started_announced":  False,
    "reminded_2h":            False,
    "reminded_30m":           False,
    "posted_result":          False,
    "three_star_seen":        set(),  # "attackerTag-defenderTag" keys
}

def reset_war(war_id: str) -> None:
    """New war detected — reset all war tracking flags."""
    war.update({
        "war_id":                war_id,
        "preparation_announced": False,
        "war_started_announced": False,
        "reminded_2h":           False,
        "reminded_30m":          False,
        "posted_result":         False,
        "three_star_seen":       set(),
    })
    log.info("Urush holati yangilandi (war_id=%s)", war_id)

def is_new_war(war_id: str) -> bool:
    return war["war_id"] != war_id

# ── Member state ──────────────────────────────────────────────────────────────
members: dict[str, str] = {}   # tag → name
members_initialized: bool = False

def init_members(current: dict[str, str]) -> None:
    """First-run snapshot — don't announce anything, just record."""
    global members, members_initialized
    members             = current
    members_initialized = True
    log.info("A'zolar boshlang'ich holati saqlandi (%d ta).", len(members))

def diff_members(current: dict[str, str]) -> tuple[set, set]:
    """Return (joined_tags, left_tags) compared to last known state."""
    joined = current.keys() - members.keys()
    left   = members.keys() - current.keys()
    return joined, left

def update_members(current: dict[str, str]) -> None:
    global members
    members = current