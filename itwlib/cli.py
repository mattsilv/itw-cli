"""Argument dispatch / entrypoint. Hand-rolled argv parsing — no dependency.

Surface is deliberately tiny: a single name lookup plus the leaderboard.
  itw "<name>"            profile card (avatar + strength + per-model bars)
  itw "<name>" --detail   + per-model evidence & tiers
  itw board [slice]       leaderboard
"""
from __future__ import annotations

import sys

from rich.panel import Panel

from itwlib import __version__
from itwlib.config import console
from itwlib import commands

USAGE = Panel(
    "[bold bright_magenta]itw[/] — intheweights.com CLI\n\n"
    "[cyan]itw [bold]\"<name>\"[/bold][/]            ⭐ profile card — avatar + strength + model bars\n"
    "[cyan]itw [bold]\"<name>\"[/bold] --detail[/]   per-model evidence & tiers\n"
    "[cyan]itw top[/]                  the top 20 as a pixel-avatar gallery\n"
    "[cyan]itw board[/] [dim][slice][/]        leaderboard table\n\n"
    "[dim]flags:[/] [cyan]--detail[/] · [cyan]--version[/] · [cyan]-h/--help[/]\n"
    "[dim]read-only — never writes to the site. unofficial & unaffiliated.[/]",
    title="usage", border_style="bright_magenta")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if "--version" in args:
        console.print(f"itw {__version__}")
        return 0

    # global flags, stripped before positional parsing
    detail = "--detail" in args
    args = [a for a in args if a != "--detail"]

    cmd = args[0] if args else "help"

    if cmd in ("-h", "--help", "help"):
        console.print(USAGE)
        return 0

    if cmd == "top":
        commands.cmd_top()
        return 0

    if cmd == "board":
        commands.cmd_board(args[1] if len(args) > 1 else "top")
        return 0

    # everything else is a name lookup (quotes optional: `itw paul mccartney`)
    name = " ".join(args).strip()
    if not name:
        console.print(USAGE)
        return 0
    commands.cmd_lookup(name, detail=detail)
    return 0
