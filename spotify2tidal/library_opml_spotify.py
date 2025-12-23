"""Spotify-side OPML export functions for podcasts."""

from __future__ import annotations

import datetime
import logging
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, List, Optional
from xml.dom import minidom

import requests

logger = logging.getLogger(__name__)


def normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, remove non-alnum."""
    if not text:
        return ""
    # Remove common suffixes that differ between platforms
    text = re.sub(r"\s*\(?Podcast\)?|\s*Show\s*$", "", text, flags=re.IGNORECASE)
    return "".join(c.lower() for c in text if c.isalnum())


def score_match(s_name: str, s_pub: str, result: dict) -> float:
    """Score an iTunes result against Spotify show data."""
    score = 0.0

    r_name = result.get("trackName", "")
    r_pub = result.get("artistName", "")

    sn = normalize(s_name)
    rn = normalize(r_name)

    if sn == rn:
        score += 1.0
    elif sn in rn or rn in sn:
        score += 0.5

    sp = normalize(s_pub)
    rp = normalize(r_pub)

    if sp and rp:
        if sp == rp:
            score += 0.5
        elif sp in rp or rp in sp:
            score += 0.2

    return score


def extract_rss_from_text(text: str) -> Optional[str]:
    """Attempt to find an RSS feed URL in a block of text."""
    if not text:
        return None
    # Look for common RSS feed patterns
    patterns = [
        r'https?://[^\s<>"]+?\.rss',
        r'https?://[^\s<>"]+?/rss/?',
        r'https?://[^\s<>"]+?/feed/?',
        r'https?://[^\s<>"]+?/podcast/?',
        r'https?://feeds\.[^\s<>"]+',
        r'https?://[^\s<>"]+?rss[^\s<>"]*',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def resolve_rss_url(
    session: requests.Session, name: str, publisher: str = "", description: str = ""
) -> Optional[str]:
    """Search for the RSS feed URL using multiple strategies."""

    # Strategy 0: Check description first (it might have the direct link)
    desc_rss = extract_rss_from_text(description)
    if desc_rss:
        return desc_rss

    # Strategy 1: Search iTunes API - trust their ranking
    try:
        params = {"term": name, "entity": "podcast", "limit": 1}
        response = session.get("https://itunes.apple.com/search", params=params, timeout=5)
        if response.status_code == 200:
            results = response.json().get("results", [])
            if results and results[0].get("feedUrl"):
                return results[0].get("feedUrl")
    except Exception as e:
        logger.debug(f"iTunes search failed for '{name}': {e}")

    return None


def export_podcasts_opml(
    podcasts: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_podcasts.opml",
    logger: Optional[Any] = None,
) -> str | Path:
    """Export Spotify podcasts to OPML 1.0 with robust resolution."""

    root = ET.Element("opml", version="1.0")
    head = ET.SubElement(root, "head")
    title = ET.SubElement(head, "title")
    title.text = "Podcasts"
    date_created = ET.SubElement(head, "dateCreated")
    date_created.text = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    body = ET.SubElement(root, "body")

    if logger:
        logger.info(f"Resolving RSS feeds for {len(podcasts)} podcasts...")

    resolved_count = 0
    with requests.Session() as session:
        for item in podcasts:
            show = item.get("show", item)
            if not show:
                continue

            name = show.get("name", "Unknown Podcast")
            publisher = show.get("publisher", "")
            description = show.get("description", "")

            # Try to resolve real RSS feed URL
            xml_url = resolve_rss_url(session, name, publisher, description)

            if not xml_url:
                if logger:
                    logger.warning(
                        f"Skipping '{name}' - could not find RSS feed online (Spotify-exclusive?)"
                    )
                continue

            ET.SubElement(
                body,
                "outline",
                text=name,
                title=name,
                type="rss",
                xmlUrl=xml_url,
                version="RSS",
            )
            resolved_count += 1

    if logger:
        logger.success(f"Generated OPML with {resolved_count}/{len(podcasts)} resolved feeds.")

    # Use minidom to prettify the XML
    xml_string = ET.tostring(root, encoding="utf-8")
    reparsed = minidom.parseString(xml_string)
    pretty_xml = reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

    if export_dir:
        export_dir.mkdir(parents=True, exist_ok=True)
        filepath = export_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(pretty_xml)
        return filepath

    return pretty_xml
