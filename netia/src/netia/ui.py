"""Affichage dans le terminal : Markdown en direct, indicateur d'attente, outils."""

from __future__ import annotations

import difflib
from pathlib import Path

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

PREVIEW_LINES = 40


def split_ready(buffer: str) -> tuple[str, str]:
    """Coupe le texte reçu en (partie complète affichable, reste).

    On ne coupe que sur une ligne vide située hors d'un bloc de code ```, pour
    que chaque morceau soit du Markdown valide (titres, listes, code…).
    """
    in_fence = False
    cut = 0
    pos = 0
    for line in buffer.splitlines(keepends=True):
        pos += len(line)
        if not line.endswith("\n"):
            break  # ligne pas encore terminée
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            if not in_fence:
                cut = pos  # fin d'un bloc de code : on peut l'afficher
        elif not stripped and not in_fence:
            cut = pos
    return buffer[:cut], buffer[cut:]


class UI:
    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console(highlight=False)
        self._buffer = ""
        self._status = None

    # --- attente -------------------------------------------------------
    def waiting(self, message: str = "NetIA réfléchit…") -> None:
        self.stop_waiting()
        if self.console.is_terminal:
            self._status = self.console.status(f"[dim]{message}[/]", spinner="dots")
            self._status.start()

    def stop_waiting(self) -> None:
        if self._status is not None:
            self._status.stop()
            self._status = None

    # --- texte de l'IA -------------------------------------------------
    def text(self, chunk: str) -> None:
        self.stop_waiting()
        self._buffer += chunk
        ready, self._buffer = split_ready(self._buffer)
        if ready.strip():
            self.console.print(Markdown(ready))

    def flush(self) -> None:
        self.stop_waiting()
        if self._buffer.strip():
            self.console.print(Markdown(self._buffer))
        self._buffer = ""

    # --- messages divers -----------------------------------------------
    def info(self, message: str) -> None:
        self.flush()
        self.console.print(f"[dim]{message}[/]")

    def warn(self, message: str) -> None:
        self.flush()
        self.console.print(f"[yellow]⚠  {message}[/]")

    def error(self, message: str) -> None:
        self.flush()
        self.console.print(f"[bold red]✖  {message}[/]")

    # --- outils --------------------------------------------------------
    def tool_header(self, label: str, detail: str = "") -> None:
        self.flush()
        line = Text("● ", style="cyan")
        line.append(label, style="bold cyan")
        if detail:
            line.append(f"  {detail}", style="cyan")
        self.console.print(line)

    def tool_result(self, summary: str, ok: bool = True) -> None:
        style = "dim" if ok else "red"
        for i, line in enumerate(summary.splitlines() or [""]):
            prefix = "  ⎿ " if i == 0 else "    "
            self.console.print(Text(prefix + line, style=style))

    def preview_file(self, path: Path, content: str) -> None:
        lines = content.splitlines()
        shown = "\n".join(lines[:PREVIEW_LINES])
        lexer = Syntax.guess_lexer(str(path), code=shown) if shown else "text"
        body = Syntax(shown or " ", lexer, line_numbers=True, word_wrap=True)
        more = f" (+{len(lines) - PREVIEW_LINES} lignes)" if len(lines) > PREVIEW_LINES else ""
        self.console.print(Panel(body, title=f"{path}{more}", title_align="left", border_style="dim"))

    def preview_diff(self, path: Path, old: str, new: str) -> None:
        diff = "".join(
            difflib.unified_diff(
                old.splitlines(keepends=True), new.splitlines(keepends=True),
                fromfile=f"{path} (avant)", tofile=f"{path} (après)", n=2,
            )
        )
        lines = diff.splitlines()
        if len(lines) > PREVIEW_LINES * 2:
            lines = lines[: PREVIEW_LINES * 2] + ["…"]
        self.console.print(Syntax("\n".join(lines) or "(aucun changement)", "diff", word_wrap=True))

    def preview_command(self, command: str) -> None:
        self.console.print(Panel(Syntax(command, "bash", word_wrap=True), border_style="dim"))

    def ask(self, prompt: str) -> str:
        self.flush()
        return self.console.input(prompt)
