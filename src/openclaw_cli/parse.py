"""Parse OpenClaw session JSONL lines into display-friendly records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class ParsedMessage:
    """A human-readable message extracted from a session log line."""

    timestamp: datetime
    role: str  # user | assistant | toolResult
    agent: str  # agent ID (e.g. "main", "penny")
    session_id: str
    model: str | None = None
    provider: str | None = None
    text: str = ""
    cost: float | None = None
    stop_reason: str | None = None
    raw: dict = field(default_factory=dict, repr=False)


def parse_line(line: str, agent: str, session_id: str) -> ParsedMessage | None:
    """Parse a single JSONL line into a ParsedMessage, or None if not a text message."""
    try:
        obj = json.loads(line)
    except (json.JSONDecodeError, ValueError):
        return None

    if obj.get("type") != "message":
        return None

    msg = obj.get("message", {})
    role = msg.get("role", "")

    # Only care about user and assistant text messages
    if role not in ("user", "assistant"):
        return None

    # Extract text content blocks
    content = msg.get("content", [])
    text_parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text_parts.append(block.get("text", ""))
        elif isinstance(block, str):
            text_parts.append(block)

    text = "\n".join(text_parts).strip()
    if not text:
        return None

    # Timestamp
    ts_str = obj.get("timestamp", "")
    try:
        ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        ts = datetime.now(timezone.utc)

    # Cost
    usage = msg.get("usage", {})
    cost_obj = usage.get("cost", {})
    cost = cost_obj.get("total") if cost_obj else None

    return ParsedMessage(
        timestamp=ts,
        role=role,
        agent=agent,
        session_id=session_id,
        model=msg.get("model"),
        provider=msg.get("provider"),
        text=text,
        cost=cost,
        stop_reason=msg.get("stopReason"),
        raw=obj,
    )


def extract_session_id(path: Any) -> str:
    """Extract the session UUID from a file path."""
    name = str(path.name) if hasattr(path, "name") else str(path)
    return name.split(".")[0]
