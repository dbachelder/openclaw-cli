"""Tail OpenClaw session logs in real time."""

from __future__ import annotations

import os
import select
import sys
import time
from pathlib import Path

import click
from rich.console import Console
from rich.text import Text

from openclaw_cli.parse import ParsedMessage, extract_session_id, parse_line
from openclaw_cli.paths import get_agents, get_session_files


console = Console()


def format_message(msg: ParsedMessage, *, show_session: bool = True) -> Text:
    """Format a ParsedMessage for terminal display."""
    local_ts = msg.timestamp.astimezone()
    time_str = local_ts.strftime("%H:%M:%S")

    line = Text()

    # Timestamp
    line.append(time_str, style="dim")
    line.append(" ")

    # Agent
    line.append(f"[{msg.agent}]", style="cyan")
    line.append(" ")

    # Session (short)
    if show_session:
        short_id = msg.session_id[:8]
        line.append(f"({short_id})", style="dim")
        line.append(" ")

    # Role badge
    if msg.role == "user":
        line.append("USER ", style="bold green")
    elif msg.role == "assistant":
        model_tag = msg.model or "unknown"
        if model_tag == "delivery-mirror":
            line.append("AI(mirror) ", style="bold blue")
        else:
            line.append(f"AI({model_tag}) ", style="bold magenta")

    # Cost
    if msg.cost is not None and msg.cost > 0:
        line.append(f"${msg.cost:.4f} ", style="yellow")

    # Text (truncate long messages for tail view)
    text = msg.text
    # Strip the [Tue 2026-...] prefix from user messages for readability
    if msg.role == "user" and text.startswith("["):
        # Find "[User Message]" marker
        marker = "[User Message]"
        idx = text.find(marker)
        if idx != -1:
            text = text[idx + len(marker) :].strip()

    # Collapse to single line for tail view, truncate
    text_oneline = text.replace("\n", " ↵ ")
    max_width = max(40, (console.width or 120) - 50)
    if len(text_oneline) > max_width:
        text_oneline = text_oneline[: max_width - 1] + "…"

    line.append(text_oneline)
    return line


class SessionTailer:
    """Watch multiple session JSONL files for new messages."""

    def __init__(
        self,
        agents: list[str],
        *,
        include_deleted: bool = False,
        poll_interval: float = 0.5,
        new_files_interval: float = 5.0,
    ):
        self.agents = agents
        self.include_deleted = include_deleted
        self.poll_interval = poll_interval
        self.new_files_interval = new_files_interval

        # path -> (file handle, agent, session_id)
        self._files: dict[Path, tuple[object, str, str]] = {}
        self._last_scan = 0.0

    def _scan_files(self) -> None:
        """Discover new session files."""
        for agent in self.agents:
            for path in get_session_files(agent, include_deleted=self.include_deleted):
                if path not in self._files:
                    try:
                        fh = open(path, "r")  # noqa: SIM115
                        # Seek to end — we only want new lines
                        fh.seek(0, os.SEEK_END)
                        session_id = extract_session_id(path)
                        self._files[path] = (fh, agent, session_id)
                    except OSError:
                        pass
        self._last_scan = time.monotonic()

    def tail(self) -> None:
        """Tail all session files, yielding formatted output."""
        self._scan_files()

        agent_str = ", ".join(self.agents) if self.agents else "none"
        file_count = len(self._files)
        console.print(
            f"[bold]Tailing {file_count} sessions across agents: {agent_str}[/bold]"
        )
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        try:
            while True:
                # Periodically scan for new files
                if time.monotonic() - self._last_scan > self.new_files_interval:
                    old_count = len(self._files)
                    self._scan_files()
                    new_count = len(self._files)
                    if new_count > old_count:
                        console.print(
                            f"[dim]  + {new_count - old_count} new session(s)[/dim]"
                        )

                found_any = False
                for path, (fh, agent, session_id) in list(self._files.items()):
                    while True:
                        line = fh.readline()
                        if not line:
                            break
                        line = line.strip()
                        if not line:
                            continue
                        msg = parse_line(line, agent, session_id)
                        if msg:
                            console.print(format_message(msg))
                            found_any = True

                if not found_any:
                    # Use select on stdin for responsive Ctrl+C on some systems
                    time.sleep(self.poll_interval)

        except KeyboardInterrupt:
            console.print("\n[dim]Stopped.[/dim]")
        finally:
            for path, (fh, _, _) in self._files.items():
                try:
                    fh.close()
                except Exception:
                    pass


@click.command()
@click.option(
    "-a",
    "--agent",
    "agents",
    multiple=True,
    help="Agent ID(s) to tail. Defaults to all agents.",
)
@click.option(
    "-n",
    "--last",
    "last_n",
    default=0,
    type=int,
    help="Show last N messages before tailing.",
)
@click.option(
    "--all-roles",
    is_flag=True,
    help="Include tool results (by default only user/assistant).",
)
@click.option(
    "--no-follow",
    is_flag=True,
    help="Print recent messages and exit (don't follow).",
)
@click.option(
    "--deleted",
    is_flag=True,
    help="Include deleted session files.",
)
def tail(
    agents: tuple[str, ...],
    last_n: int,
    all_roles: bool,
    no_follow: bool,
    deleted: bool,
) -> None:
    """Tail OpenClaw session logs in real time.

    Shows user and assistant messages across all agents and sessions.
    Displays agent ID, model, cost, and message text.

    \b
    Examples:
        ocli tail                    # Tail all agents
        ocli tail -a main            # Tail only the "main" agent
        ocli tail -n 20              # Show last 20 messages, then follow
        ocli tail -n 10 --no-follow  # Show last 10 messages and exit
    """
    # Resolve agents
    agent_list = list(agents) if agents else get_agents()
    if not agent_list:
        console.print("[red]No agents found in ~/.openclaw/agents/[/red]")
        raise SystemExit(1)

    # Show last N messages if requested
    if last_n > 0:
        _show_last_n(agent_list, last_n, include_deleted=deleted)

    if no_follow:
        if last_n == 0:
            # Default to 20 when --no-follow with no -n
            _show_last_n(agent_list, 20, include_deleted=deleted)
        return

    # Real-time tail
    tailer = SessionTailer(agent_list, include_deleted=deleted)
    tailer.tail()


def _show_last_n(agents: list[str], n: int, *, include_deleted: bool = False) -> None:
    """Show the last N messages across all agents, sorted by time."""
    all_messages: list[ParsedMessage] = []

    for agent in agents:
        for path in get_session_files(agent, include_deleted=include_deleted):
            session_id = extract_session_id(path)
            try:
                # Read from the end efficiently
                lines = _tail_lines(path, max_lines=n * 3)  # over-read since many lines aren't text
                for line in lines:
                    msg = parse_line(line, agent, session_id)
                    if msg:
                        all_messages.append(msg)
            except OSError:
                pass

    # Sort by timestamp, take last N
    all_messages.sort(key=lambda m: m.timestamp)
    for msg in all_messages[-n:]:
        console.print(format_message(msg))

    if all_messages:
        console.print()


def _tail_lines(path: Path, max_lines: int = 100) -> list[str]:
    """Read the last max_lines from a file efficiently."""
    try:
        with open(path, "rb") as f:
            # Seek back in chunks to find enough lines
            f.seek(0, os.SEEK_END)
            size = f.tell()
            chunk = min(size, max_lines * 2048)  # ~2KB per line estimate
            f.seek(max(0, size - chunk))
            data = f.read().decode("utf-8", errors="replace")
            lines = data.strip().split("\n")
            return lines[-max_lines:]
    except OSError:
        return []
