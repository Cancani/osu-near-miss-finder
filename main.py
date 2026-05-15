"""
osu! Near-Miss Finder — FastAPI backend.

Fetches a user's top plays from the osu! API v2 and surfaces the ones that
ended with only a handful of misses (the "almost FC'd" plays).
"""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

load_dotenv()

CLIENT_ID = os.getenv("OSU_CLIENT_ID")
CLIENT_SECRET = os.getenv("OSU_CLIENT_SECRET")
TOKEN_URL = "https://osu.ppy.sh/oauth/token"
API_BASE = "https://osu.ppy.sh/api/v2"

VALID_MODES = {"osu", "taiko", "fruits", "mania"}
VALID_SCORE_TYPES = {"best", "recent", "firsts", "pinned"}

app = FastAPI(
    title="osu! Near-Miss Finder",
    description="Find plays you almost full-comboed.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Simple in-memory token cache (client_credentials tokens last ~24h).
_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}


async def get_access_token() -> str:
    """Get (and cache) a client-credentials access token from osu!."""
    if _token_cache["token"] and time.time() < _token_cache["expires_at"]:
        return _token_cache["token"]

    if not CLIENT_ID or not CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail=(
                "Server is missing OSU_CLIENT_ID / OSU_CLIENT_SECRET. "
                "Create an OAuth client at https://osu.ppy.sh/home/account/edit "
                "and copy the values into a .env file."
            ),
        )

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            TOKEN_URL,
            json={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": "public",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(502, f"osu! auth failed: {resp.text}")

    data = resp.json()
    _token_cache["token"] = data["access_token"]
    # Refresh a minute early to avoid edge-case expiries.
    _token_cache["expires_at"] = time.time() + data["expires_in"] - 60
    return _token_cache["token"]


async def osu_get(endpoint: str, params: dict | None = None) -> Any:
    """GET helper for the osu! API v2 with the cached bearer token."""
    token = await get_access_token()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"{API_BASE}{endpoint}",
            headers={"Authorization": f"Bearer {token}"},
            params=params or {},
        )

    if resp.status_code == 404:
        raise HTTPException(404, "Not found")
    if resp.status_code >= 400:
        raise HTTPException(resp.status_code, f"osu! API error: {resp.text}")

    return resp.json()


def slim_score(score: dict) -> dict:
    """Project a raw osu! score into a compact dict for the frontend."""
    stats = score.get("statistics", {}) or {}
    beatmap = score.get("beatmap", {}) or {}
    bset = score.get("beatmapset", {}) or {}
    covers = bset.get("covers", {}) or {}

    return {
        "id": score.get("id"),
        "miss_count": stats.get("count_miss", 0) or 0,
        "count_300": stats.get("count_300", 0) or 0,
        "count_100": stats.get("count_100", 0) or 0,
        "count_50": stats.get("count_50", 0) or 0,
        "max_combo": score.get("max_combo"),
        "accuracy": round((score.get("accuracy") or 0) * 100, 2),
        "pp": score.get("pp"),
        "rank": score.get("rank"),
        "mods": score.get("mods", []) or [],
        "created_at": score.get("created_at"),
        "score": score.get("score"),
        "beatmap": {
            "id": beatmap.get("id"),
            "version": beatmap.get("version"),
            "difficulty_rating": beatmap.get("difficulty_rating"),
            "url": beatmap.get("url"),
            "max_combo": beatmap.get("max_combo"),
            "bpm": beatmap.get("bpm"),
            "total_length": beatmap.get("total_length"),
        },
        "beatmapset": {
            "id": bset.get("id"),
            "title": bset.get("title"),
            "artist": bset.get("artist"),
            "creator": bset.get("creator"),
            "cover": covers.get("cover@2x") or covers.get("cover"),
            "list": covers.get("list@2x") or covers.get("list"),
        },
    }


@app.get("/api/near-misses/{username}")
async def near_misses(
    username: str,
    mode: str = Query("osu", description="Game mode: osu, taiko, fruits, mania"),
    score_type: str = Query("best", description="Score list: best, recent, firsts, pinned"),
    min_misses: int = Query(1, ge=0, le=999),
    max_misses: int = Query(5, ge=0, le=999),
    limit: int = Query(100, ge=1, le=200),
    include_fc: bool = Query(False, description="Include 0-miss plays too"),
):
    """Return a user's plays that finished with `min_misses..max_misses` misses."""
    if mode not in VALID_MODES:
        raise HTTPException(400, f"Invalid mode '{mode}'. Use one of {sorted(VALID_MODES)}")
    if score_type not in VALID_SCORE_TYPES:
        raise HTTPException(400, f"Invalid score_type '{score_type}'. Use one of {sorted(VALID_SCORE_TYPES)}")
    if min_misses > max_misses:
        raise HTTPException(400, "min_misses must be <= max_misses")

    # Look up the user (by username, with mode-specific stats).
    try:
        user = await osu_get(f"/users/{username}/{mode}", {"key": "username"})
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(404, f"User '{username}' not found")
        raise

    # osu! API caps `limit` at 100 per request, but you can paginate with `offset`.
    collected: list[dict] = []
    offset = 0
    remaining = limit
    while remaining > 0:
        page_size = min(100, remaining)
        page = await osu_get(
            f"/users/{user['id']}/scores/{score_type}",
            {"mode": mode, "limit": page_size, "offset": offset},
        )
        if not page:
            break
        collected.extend(page)
        if len(page) < page_size:
            break
        offset += page_size
        remaining -= page_size

    # Filter and slim.
    lo = 0 if include_fc else min_misses
    results = []
    for score in collected:
        stats = score.get("statistics") or {}
        misses = stats.get("count_miss", 0) or 0
        if lo <= misses <= max_misses:
            results.append(slim_score(score))

    # Sort: by miss count asc, then pp desc.
    results.sort(key=lambda s: (s["miss_count"], -(s["pp"] or 0)))

    return {
        "user": {
            "id": user.get("id"),
            "username": user.get("username"),
            "avatar_url": user.get("avatar_url"),
            "country_code": user.get("country_code"),
            "global_rank": (user.get("statistics") or {}).get("global_rank"),
            "pp": (user.get("statistics") or {}).get("pp"),
        },
        "query": {
            "mode": mode,
            "score_type": score_type,
            "min_misses": min_misses,
            "max_misses": max_misses,
            "limit": limit,
            "include_fc": include_fc,
            "scanned": len(collected),
        },
        "count": len(results),
        "scores": results,
    }


@app.get("/api/health")
async def health():
    return {"ok": True, "configured": bool(CLIENT_ID and CLIENT_SECRET)}


# Serve the frontend (must be last so /api routes match first).
app.mount("/", StaticFiles(directory="static", html=True), name="static")