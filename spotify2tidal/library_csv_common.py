"""Common helpers for exporting library data to CSV.

This module intentionally contains only the generic CSV writer and shared
sanitization/dir helpers. Platform-specific exports live in sibling modules.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


def ensure_dir(path: Path) -> Path:
    """Ensure directory exists."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_csv_cell(value: Any) -> Any:
    """Mitigate CSV/Excel formula injection."""
    if value is None:
        return ""
    if not isinstance(value, str):
        return value

    stripped = value.lstrip()
    if stripped and stripped[0] in ("=", "+", "-", "@"):
        return "'" + value
    return value


def export_items(
    items: List[Any],
    field_extractors: Dict[str, Callable[[Any], Any]],
    export_dir: Optional[Path] = None,
    filename: str = "export.csv",
) -> str | Path:
    """Generic CSV exporter for any item type."""
    output = io.StringIO()
    writer = csv.writer(output)

    headers = list(field_extractors.keys())
    writer.writerow(headers)

    for item in items:
        if not item:
            continue
        row: list[Any] = []
        for _, extractor in field_extractors.items():
            try:
                value = extractor(item)
                if value is None:
                    row.append("")
                elif isinstance(value, (int, float)):
                    row.append(value)
                else:
                    row.append(_sanitize_csv_cell(str(value)))
            except Exception:
                row.append("")
        writer.writerow(row)

    content = output.getvalue()
    if export_dir:
        ensure_dir(export_dir)
        filepath = export_dir / filename
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            f.write(content)
        return filepath

    return content
