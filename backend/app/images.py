"""
Pictures for dishes and exercises. spec/in-progress/today-plan.md.

From **Wikimedia Commons**, under a free licence, with the credit kept beside
the URL — a picture is shown with whose it is, or not at all. A general image
search was ruled out: its results are other people's photos with no permission
to show them.

A lookup is found once and stored on the row (`image_url`, `image_credit`),
and stamped `image_looked_at` either way, so a name Commons has nothing for is
not searched again on every open. A picture is never load-bearing: anything
that goes wrong here leaves the card drawing its coin, as it always has.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx

log = logging.getLogger(__name__)

COMMONS = "https://commons.wikimedia.org/w/api.php"
#: Wikimedia asks every client to name itself.
AGENT = "Spica/0.1 (a personal app; picture lookup for its own dish library)"
#: A name with no match is looked for again after this, not before.
LOOK_AGAIN = timedelta(days=30)
TIMEOUT = 6.0
BITMAPS = ("image/jpeg", "image/png", "image/webp")


@dataclass(frozen=True)
class Picture:
    url: str
    credit: str


def _plain(s: str) -> str:
    """Commons metadata is HTML — an artist is often a link. Words only."""
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def free(licence: str) -> bool:
    """The licences a photo may be shown under with a credit: CC0, CC BY,
    CC BY-SA, public domain. Non-commercial or no-derivatives are not on
    Commons at all, but the check does not rely on that."""
    lic = licence.lower()
    if "nc" in re.split(r"[\s\-]+", lic) or "nd" in re.split(r"[\s\-]+", lic):
        return False
    return lic.startswith(("cc0", "cc by", "cc-by", "public domain", "pd"))


async def _query(text: str) -> dict:
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"{text} filetype:bitmap", "gsrlimit": 8,
        "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiurlwidth": 640,
    }
    async with httpx.AsyncClient(timeout=TIMEOUT, headers={"User-Agent": AGENT}) as c:
        r = await c.get(COMMONS, params=params)
        r.raise_for_status()
        return r.json()


#: Words that say nothing about what is in a photo.
_FILLER = {"with", "and", "the", "for", "style", "home", "homemade", "food", "dish", "exercise",
           "jpg", "jpeg", "png", "webp", "file", "img", "photo", "image"}


def _words(s: str) -> set[str]:
    return {w for w in re.split(r"[^a-z]+", s.lower()) if len(w) >= 3 and w not in _FILLER}


def pick(data: dict, name: str = "") -> Picture | None:
    """The result that is a photo under a free licence and shares the most
    words with the name — a search for *chicken curry with roti* that ranks a
    photo of peas first must not put peas on the card. With a name given, a
    photo sharing none of its words is no match at all."""
    pages = sorted(((data.get("query") or {}).get("pages") or {}).values(),
                   key=lambda p: p.get("index", 99))
    wanted = _words(name)
    if wanted:
        scored = [(len(wanted & _words(p.get("title", ""))), p) for p in pages]
        pages = [p for s, p in sorted(scored, key=lambda x: -x[0]) if s > 0]
    for p in pages:
        info = (p.get("imageinfo") or [{}])[0]
        if info.get("mime") not in BITMAPS:
            continue
        meta = info.get("extmetadata") or {}
        licence = _plain((meta.get("LicenseShortName") or {}).get("value", ""))
        if not free(licence):
            continue
        url = info.get("thumburl") or info.get("url")
        if not url:
            continue
        artist = _plain((meta.get("Artist") or {}).get("value", "")) or "unknown"
        return Picture(url, f"Photo: {artist[:60]}, {licence} · Wikimedia Commons")
    return None


async def search(name: str, hint: str = "") -> Picture | None:
    """The name with its kind of thing first ("paneer bhurji food"), then the
    name alone. Two requests at most."""
    for text in ([f"{name} {hint}"] if hint else []) + [name]:
        got = pick(await _query(text), name)
        if got:
            return got
    return None


#: Ideas are not rows, so their pictures are kept here for the life of the
#: process: the same idea tomorrow is not searched again.
_ideas: dict[str, Picture | None] = {}


def due(row) -> bool:
    """Whether a row should be looked up now."""
    if row.image_url:
        return False
    looked = row.image_looked_at
    return looked is None or datetime.now(UTC) - looked > LOOK_AGAIN


async def fill(rows: list, ideas: list[str], hint: str) -> dict[str, Picture | None]:
    """Look up every row that is due and every idea not seen yet, at once.
    Rows are written in place (the caller commits); ideas come back by name."""
    rows = [r for r in rows if due(r)]
    fresh = [n for n in dict.fromkeys(ideas) if n.lower() not in _ideas]
    names = [r.name for r in rows] + fresh

    async def one(n: str) -> Picture | None:
        try:
            return await search(n, hint)
        except Exception:  # noqa: BLE001 — a picture is never load-bearing
            log.warning("picture lookup failed for %r", n, exc_info=True)
            return None

    found = await asyncio.gather(*(one(n) for n in names))
    now = datetime.now(UTC)
    for r, pic in zip(rows, found[:len(rows)]):
        r.image_looked_at = now
        if pic:
            r.image_url, r.image_credit = pic.url, pic.credit
    for n, pic in zip(fresh, found[len(rows):]):
        _ideas[n.lower()] = pic
    return {n: _ideas.get(n.lower()) for n in ideas}
