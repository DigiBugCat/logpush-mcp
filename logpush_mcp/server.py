"""FastMCP server for Cloudflare logpush R2 reader."""

from typing import Optional

from fastmcp import FastMCP

from logpush_mcp.log_parser import (
    compute_stats,
    filter_entries,
    format_entry_detail,
    format_entry_summary,
    parse_ndjson,
)
from logpush_mcp.r2_client import get_client

mcp = FastMCP("Logpush")


@mcp.tool()
def list_log_dates(
    environment: Optional[str] = None,
    limit: int = 30,
) -> dict:
    """
    List available date folders in the logpush R2 bucket.

    Args:
        environment: Filter by environment (production, staging). None for all.
        limit: Maximum number of dates to return (default 30).

    Returns:
        Dict with dates array containing date, environment, and prefix.
    """
    client = get_client()
    dates = client.list_dates(environment=environment, limit=limit)

    return {
        "dates": [
            {
                "date": d.date,
                "environment": d.environment,
                "prefix": d.prefix,
            }
            for d in dates
        ],
        "count": len(dates),
    }


@mcp.tool()
def list_log_files(
    date: str,
    environment: str = "production",
    limit: int = 50,
    cursor: Optional[str] = None,
) -> dict:
    """
    List log files for a specific date.

    Args:
        date: Date in YYYYMMDD format (e.g., "20260111").
        environment: Environment (production or staging).
        limit: Maximum number of files to return (default 50).
        cursor: Pagination cursor from previous response.

    Returns:
        Dict with files array, count, and next_cursor for pagination.
    """
    client = get_client()
    files, next_cursor = client.list_files(
        date=date,
        environment=environment,
        limit=limit,
        continuation_token=cursor,
    )

    return {
        "files": [
            {
                "key": f.key,
                "size": f.size,
                "last_modified": f.last_modified.isoformat(),
                "start_time": f.start_time,
                "end_time": f.end_time,
            }
            for f in files
        ],
        "count": len(files),
        "next_cursor": next_cursor,
    }


@mcp.tool()
def read_log_file(path: str, limit: int = 100) -> dict:
    """
    Read and parse a specific log file from R2.

    Args:
        path: Full object path/key (e.g., "production/20260111/filename.log.gz").
        limit: Maximum number of entries to return (default 100).

    Returns:
        Dict with entries array and count.
    """
    client = get_client()
    content = client.get_file_content(path)
    entries = parse_ndjson(content)

    return {
        "entries": [format_entry_detail(e) for e in entries[:limit]],
        "count": len(entries),
        "truncated": len(entries) > limit,
    }


@mcp.tool()
def search_logs(
    date: str,
    environment: str = "production",
    script_name: Optional[str] = None,
    status_code: Optional[int] = None,
    status_gte: Optional[int] = None,
    status_lt: Optional[int] = None,
    outcome: Optional[str] = None,
    search_text: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """
    Search logs with filters.

    Args:
        date: Date in YYYYMMDD format.
        environment: Environment (production or staging).
        script_name: Filter by worker script name.
        status_code: Filter by exact HTTP status code.
        status_gte: Filter by status code >= value (e.g., 400 for errors).
        status_lt: Filter by status code < value.
        outcome: Filter by outcome ("ok" or "exception").
        search_text: Search in URL and log messages.
        limit: Maximum entries to return (default 50).

    Returns:
        Dict with matching entries and count.
    """
    client = get_client()

    # Get all files for the date
    files, _ = client.list_files(date=date, environment=environment, limit=100)

    all_entries = []
    for f in files:
        content = client.get_file_content(f.key)
        entries = parse_ndjson(content)
        all_entries.extend(entries)

        # Stop if we have enough entries after filtering
        filtered = filter_entries(
            all_entries,
            script_name=script_name,
            status_code=status_code,
            status_gte=status_gte,
            status_lt=status_lt,
            outcome=outcome,
            search_text=search_text,
        )
        if len(filtered) >= limit * 2:
            break

    # Final filter and limit
    filtered = filter_entries(
        all_entries,
        script_name=script_name,
        status_code=status_code,
        status_gte=status_gte,
        status_lt=status_lt,
        outcome=outcome,
        search_text=search_text,
    )

    # Sort by timestamp descending
    filtered.sort(key=lambda e: e.EventTimestampMs, reverse=True)

    return {
        "entries": [format_entry_summary(e) for e in filtered[:limit]],
        "count": len(filtered),
        "truncated": len(filtered) > limit,
        "files_scanned": len(files),
    }


@mcp.tool()
def get_log_stats(
    date: str,
    environment: str = "production",
) -> dict:
    """
    Get aggregated statistics for logs on a specific date.

    Args:
        date: Date in YYYYMMDD format.
        environment: Environment (production or staging).

    Returns:
        Dict with statistics including request counts by worker, status distribution, error rate.
    """
    client = get_client()

    # Get all files for the date
    files, _ = client.list_files(date=date, environment=environment, limit=200)

    all_entries = []
    for f in files:
        content = client.get_file_content(f.key)
        entries = parse_ndjson(content)
        all_entries.extend(entries)

    stats = compute_stats(all_entries)
    stats["date"] = date
    stats["environment"] = environment
    stats["files_scanned"] = len(files)

    return stats


@mcp.tool()
def get_errors(
    date: str,
    environment: str = "production",
    script_name: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """
    Get error logs and exceptions for a specific date.

    Args:
        date: Date in YYYYMMDD format.
        environment: Environment (production or staging).
        script_name: Filter by worker script name (optional).
        limit: Maximum entries to return (default 50).

    Returns:
        Dict with error entries including exceptions and error-level logs.
    """
    client = get_client()

    # Get all files for the date
    files, _ = client.list_files(date=date, environment=environment, limit=100)

    all_entries = []
    for f in files:
        content = client.get_file_content(f.key)
        entries = parse_ndjson(content)
        all_entries.extend(entries)

    # Filter for errors
    filtered = filter_entries(
        all_entries,
        script_name=script_name,
        errors_only=True,
    )

    # Sort by timestamp descending
    filtered.sort(key=lambda e: e.EventTimestampMs, reverse=True)

    return {
        "entries": [format_entry_detail(e) for e in filtered[:limit]],
        "count": len(filtered),
        "truncated": len(filtered) > limit,
    }


@mcp.tool()
def get_latest(
    environment: str = "production",
    script_name: Optional[str] = None,
    limit: int = 50,
) -> dict:
    """
    Get the most recent log entries.

    Args:
        environment: Environment (production or staging).
        script_name: Filter by worker script name (optional).
        limit: Maximum entries to return (default 50).

    Returns:
        Dict with the most recent log entries.
    """
    client = get_client()

    # Get the most recent files
    files = client.get_latest_files(environment=environment, count=5)

    if not files:
        return {
            "entries": [],
            "count": 0,
            "message": "No log files found",
        }

    all_entries = []
    for f in files:
        content = client.get_file_content(f.key)
        entries = parse_ndjson(content)
        all_entries.extend(entries)

    # Filter by script name if provided
    if script_name:
        all_entries = filter_entries(all_entries, script_name=script_name)

    # Sort by timestamp descending
    all_entries.sort(key=lambda e: e.EventTimestampMs, reverse=True)

    return {
        "entries": [format_entry_summary(e) for e in all_entries[:limit]],
        "count": len(all_entries),
        "truncated": len(all_entries) > limit,
        "files_read": [f.key for f in files],
    }


def main():
    """Run the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
