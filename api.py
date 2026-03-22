"""
api.py — Clash of Clans API so'rovlari
"""

import logging

import aiohttp

from config import CLAN_TAG, COC_BASE, COC_HEADERS

log = logging.getLogger(__name__)


def encode_tag(tag: str) -> str:
    return tag.strip().upper().replace("#", "%23")


async def _get(session: aiohttp.ClientSession, path: str):
    """Base GET — returns parsed JSON or None on error."""
    try:
        async with session.get(
            f"{COC_BASE}{path}",
            headers=COC_HEADERS,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as r:
            if r.status == 200:
                return await r.json()
            log.warning("CoC API %s → HTTP %s", path, r.status)
    except Exception as exc:
        log.error("CoC so'rov xatosi %s: %s", path, exc)
    return None


async def fetch_current_war(session: aiohttp.ClientSession) -> dict | None:
    return await _get(session, f"/clans/{encode_tag(CLAN_TAG)}/currentwar")


async def fetch_war_log(session: aiohttp.ClientSession) -> list:
    data = await _get(session, f"/clans/{encode_tag(CLAN_TAG)}/warlog?limit=5")
    return (data or {}).get("items", [])


async def fetch_player(session: aiohttp.ClientSession, tag: str) -> dict | None:
    return await _get(session, f"/players/{encode_tag(tag)}")


async def fetch_clan_members(session: aiohttp.ClientSession) -> list:
    data = await _get(session, f"/clans/{encode_tag(CLAN_TAG)}/members?limit=50")
    return (data or {}).get("items", [])
