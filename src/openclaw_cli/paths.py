"""Discover OpenClaw session log paths."""

from __future__ import annotations

from pathlib import Path


OPENCLAW_DIR = Path.home() / ".openclaw"
AGENTS_DIR = OPENCLAW_DIR / "agents"


def get_agents() -> list[str]:
    """Return list of agent IDs that have session directories."""
    if not AGENTS_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in AGENTS_DIR.iterdir()
        if d.is_dir() and (d / "sessions").is_dir()
    )


def get_session_dir(agent: str) -> Path:
    """Return the sessions directory for an agent."""
    return AGENTS_DIR / agent / "sessions"


def get_session_files(agent: str, include_deleted: bool = False) -> list[Path]:
    """Return all .jsonl session files for an agent, sorted by mtime (newest first)."""
    session_dir = get_session_dir(agent)
    if not session_dir.is_dir():
        return []
    files = []
    for f in session_dir.iterdir():
        if not f.name.endswith(".jsonl"):
            continue
        if not include_deleted and ".deleted." in f.name:
            continue
        files.append(f)
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)
