"""Spotify-side OPML export functions for podcasts."""

from __future__ import annotations

import datetime
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional
from xml.dom import minidom


def export_podcasts_opml(
    podcasts: List[dict],
    export_dir: Optional[Path] = None,
    filename: str = "spotify_podcasts.opml",
) -> str | Path:
    """Export Spotify podcasts to OPML 2.0."""

    root = ET.Element("opml", version="2.0")
    head = ET.SubElement(root, "head")
    title = ET.SubElement(head, "title")
    title.text = "Spotify Podcast Subscriptions"
    date_created = ET.SubElement(head, "dateCreated")
    date_created.text = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0000")

    body = ET.SubElement(root, "body")

    for item in podcasts:
        show = item.get("show", item)
        if not show:
            continue

        name = show.get("name", "Unknown Podcast")
        spotify_url = show.get("external_urls", {}).get("spotify", "")
        # Since we don't have the RSS feed, we use the Spotify URL as a placeholder
        # Most podcast apps can use the title to search if the xmlUrl isn't a
        # direct feed.

        ET.SubElement(
            body,
            "outline",
            text=name,
            title=name,
            type="rss",
            xmlUrl=spotify_url,
            htmlUrl=spotify_url,
        )

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
