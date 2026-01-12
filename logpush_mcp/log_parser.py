"""Parser for NDJSON logpush files and filtering utilities."""

import json
from collections import Counter
from typing import Optional

from logpush_mcp.types import LogEntry


def parse_ndjson(content: str) -> list[LogEntry]:
    """Parse NDJSON content into LogEntry objects.

    Args:
        content: NDJSON string (one JSON object per line).

    Returns:
        List of LogEntry objects.
    """
    entries = []
    for line in content.strip().split("\n"):
        if not line:
            continue
        try:
            data = json.loads(line)
            entries.append(LogEntry.model_validate(data))
        except (json.JSONDecodeError, ValueError):
            # Skip malformed lines
            continue
    return entries


def filter_entries(
    entries: list[LogEntry],
    script_name: Optional[str] = None,
    status_code: Optional[int] = None,
    status_gte: Optional[int] = None,
    status_lt: Optional[int] = None,
    outcome: Optional[str] = None,
    search_text: Optional[str] = None,
    errors_only: bool = False,
) -> list[LogEntry]:
    """Filter log entries by various criteria.

    Args:
        entries: List of LogEntry objects to filter.
        script_name: Filter by worker script name.
        status_code: Filter by exact status code.
        status_gte: Filter by status code >= value.
        status_lt: Filter by status code < value.
        outcome: Filter by outcome (ok, exception).
        search_text: Search in URL and log messages.
        errors_only: Only return entries with errors.

    Returns:
        Filtered list of LogEntry objects.
    """
    filtered = entries

    if script_name:
        filtered = [e for e in filtered if e.ScriptName == script_name]

    if status_code is not None:
        filtered = [e for e in filtered if e.status == status_code]

    if status_gte is not None:
        filtered = [e for e in filtered if e.status >= status_gte]

    if status_lt is not None:
        filtered = [e for e in filtered if e.status < status_lt]

    if outcome:
        filtered = [e for e in filtered if e.Outcome == outcome]

    if search_text:
        search_lower = search_text.lower()
        filtered = [
            e
            for e in filtered
            if search_lower in e.url.lower() or search_lower in e.log_text.lower()
        ]

    if errors_only:
        filtered = [e for e in filtered if e.has_errors]

    return filtered


def compute_stats(entries: list[LogEntry]) -> dict:
    """Compute statistics for a list of log entries.

    Args:
        entries: List of LogEntry objects.

    Returns:
        Dict with statistics.
    """
    if not entries:
        return {
            "total_requests": 0,
            "by_worker": {},
            "by_status": {},
            "by_outcome": {},
            "error_count": 0,
            "error_rate": 0.0,
        }

    worker_counts = Counter(e.ScriptName for e in entries)
    status_counts = Counter(e.status for e in entries)
    outcome_counts = Counter(e.Outcome for e in entries)
    error_count = sum(1 for e in entries if e.has_errors)

    return {
        "total_requests": len(entries),
        "by_worker": dict(worker_counts),
        "by_status": {str(k): v for k, v in sorted(status_counts.items())},
        "by_outcome": dict(outcome_counts),
        "error_count": error_count,
        "error_rate": round(error_count / len(entries) * 100, 2),
    }


def format_entry_summary(entry: LogEntry) -> dict:
    """Format a log entry for display.

    Args:
        entry: LogEntry to format.

    Returns:
        Dict with formatted entry data.
    """
    return {
        "timestamp": entry.timestamp.isoformat(),
        "script": entry.ScriptName,
        "method": entry.Event.Request.Method,
        "url": entry.url,
        "status": entry.status,
        "outcome": entry.Outcome,
        "ray_id": entry.Event.RayID,
        "has_errors": entry.has_errors,
        "exception_count": len(entry.Exceptions),
        "log_count": len(entry.Logs),
    }


def format_entry_detail(entry: LogEntry) -> dict:
    """Format a log entry with full details.

    Args:
        entry: LogEntry to format.

    Returns:
        Dict with full entry data.
    """
    return {
        "timestamp": entry.timestamp.isoformat(),
        "script": entry.ScriptName,
        "method": entry.Event.Request.Method,
        "url": entry.url,
        "status": entry.status,
        "outcome": entry.Outcome,
        "ray_id": entry.Event.RayID,
        "cpu_time_ms": entry.CPUTimeMs,
        "wall_time_ms": entry.WallTimeMs,
        "exceptions": [
            {"name": ex.Name, "message": ex.Message} for ex in entry.Exceptions
        ],
        "logs": [
            {
                "level": log.Level,
                "message": log.text,
                "timestamp_ms": log.TimestampMs,
            }
            for log in entry.Logs
        ],
    }
