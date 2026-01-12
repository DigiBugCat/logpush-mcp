"""Pydantic models for Cloudflare Workers trace events."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class EventRequest(BaseModel):
    """HTTP request details from the trace event."""

    URL: str = ""
    Method: str = ""


class EventResponse(BaseModel):
    """HTTP response details from the trace event."""

    Status: int = 0


class TraceEvent(BaseModel):
    """The event that triggered the worker invocation."""

    RayID: str = ""
    Request: EventRequest = Field(default_factory=EventRequest)
    Response: EventResponse = Field(default_factory=EventResponse)


class LogMessage(BaseModel):
    """A console log message emitted during invocation."""

    Level: str = "log"
    Message: list[str] = Field(default_factory=list)
    TimestampMs: int = 0

    @property
    def text(self) -> str:
        """Get the log message as a single string."""
        return " ".join(self.Message)


class LogException(BaseModel):
    """An uncaught exception during invocation."""

    Name: str = ""
    Message: str = ""


class ScriptVersionInfo(BaseModel):
    """Version info for the worker script."""

    Id: str = ""


class LogEntry(BaseModel):
    """A single trace event log entry from Cloudflare logpush."""

    Event: TraceEvent = Field(default_factory=TraceEvent)
    EventTimestampMs: int = 0
    EventType: str = "fetch"
    Outcome: str = "ok"
    Exceptions: list[LogException] = Field(default_factory=list)
    Logs: list[LogMessage] = Field(default_factory=list)
    ScriptName: str = ""
    ScriptTags: list[str] = Field(default_factory=list)
    ScriptVersion: Optional[ScriptVersionInfo] = None
    CPUTimeMs: Optional[int] = None
    WallTimeMs: Optional[int] = None
    DispatchNamespace: Optional[str] = None
    Entrypoint: Optional[str] = None

    @property
    def timestamp(self) -> datetime:
        """Get the event timestamp as a datetime."""
        return datetime.fromtimestamp(self.EventTimestampMs / 1000)

    @property
    def url(self) -> str:
        """Get the request URL."""
        return self.Event.Request.URL

    @property
    def status(self) -> int:
        """Get the response status code."""
        return self.Event.Response.Status

    @property
    def has_errors(self) -> bool:
        """Check if this entry has errors or exceptions."""
        if self.Outcome == "exception":
            return True
        if self.Exceptions:
            return True
        for log in self.Logs:
            if log.Level in ("error", "warn"):
                return True
        return False

    @property
    def log_text(self) -> str:
        """Get all log messages as a single string."""
        return "\n".join(log.text for log in self.Logs)


class LogFile(BaseModel):
    """Metadata about a log file in R2."""

    key: str
    size: int
    last_modified: datetime
    start_time: Optional[str] = None
    end_time: Optional[str] = None

    @classmethod
    def from_key(cls, key: str, size: int, last_modified: datetime) -> LogFile:
        """Create LogFile from R2 object key, extracting time range from filename."""
        # Filename format: {start_ts}_{end_ts}_{hash}.log.gz
        filename = key.split("/")[-1]
        parts = filename.replace(".log.gz", "").split("_")
        start_time = parts[0] if len(parts) >= 2 else None
        end_time = parts[1] if len(parts) >= 2 else None
        return cls(
            key=key,
            size=size,
            last_modified=last_modified,
            start_time=start_time,
            end_time=end_time,
        )


class DateFolder(BaseModel):
    """A date folder in the R2 bucket."""

    date: str  # YYYYMMDD format
    environment: str  # production, staging, or root
    prefix: str  # Full prefix path
    file_count: Optional[int] = None
