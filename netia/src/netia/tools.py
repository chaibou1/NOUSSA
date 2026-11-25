"""Outils de l'agent : fichiers, dossiers et commandes, limités au dossier de travail.

Chaque écriture de fichier et chaque commande doit être validée par
l'utilisateur (sauf avec --yes, ou après avoir répondu « toujours »).
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from netia.ui import UI

MAX_READ_BYTES = 200_000
MAX_OUTPUT_CHARS = 15_000
MAX_LIST_ENTRIES = 300
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache"}

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "list_directory",
        "description": "Liste le contenu d'un dossier (relatif au dossier de travail). "
        "Les dossiers finissent par '/'.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Dossier à lister, '.' par défaut"},
            },
            "required": [],
            "additionalProperties": False,
        },
    },
    {
        "name": "read_file",
        "description": "Lit un fichier texte et renvoie son contenu.",
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Chemin du fichier"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "create_directory",
        "description": "Crée un dossier (et ses dossiers parents si besoin).",
        "schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Dossier à créer"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "write_file",
        "description": "Crée un fichier ou remplace entièrement son contenu. Les dossiers "
        "parents sont créés automatiquement. Pour une petite modification d'un fichier "
        "existant, préfère edit_file.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Chemin du fichier"},
                "content": {"type": "string", "description": "Contenu complet du fichier"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    },
    {
        "name": "edit_file",
        "description": "Remplace un passage exact d'un fichier existant par un nouveau texte. "
        "old_text doit apparaître une seule fois dans le fichier : inclus assez de "
        "contexte pour qu'il soit unique.",
        "schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "old_text": {"type": "string", "description": "Texte exact à remplacer"},
                "new_text": {"type": "string", "description": "Texte de remplacement"},
            },
            "required": ["path", "old_text", "new_text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "run_command",
        "description": "Exécute une commande shell non interactive dans le dossier de travail "
        "et renvoie sa sortie (stdout + stderr) et son code de retour. Pas d'entrée "
        "clavier possible : évite les commandes qui attendent une saisie.",
        "schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Commande à exécuter"},
                "timeout": {
                    "type": "integer",
                    "description": "Délai max en secondes (défaut 120, max 600)",
                },
            },
            "required": ["command"],
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = {spec["name"] for spec in TOOL_SPECS}
NEEDS_APPROVAL = {"write_file", "edit_file", "run_command"}
_TYPES = {"string": str, "integer": int}


@dataclass
class ToolCall:
    id: str
    name: str
    input: Any  # dict, ou None si le JSON reçu était invalide
    raw: str = ""


@dataclass
class ToolResult:
    call_id: str
    content: str
    is_error: bool = False


class ToolError(Exception):
    pass


def validate(name: str, data: Any) -> str | None:
    """Vérifie les arguments reçus par rapport au schéma. Renvoie une erreur ou None."""
    spec = next((s for s in TOOL_SPECS if s["name"] == name), None)
    if spec is None:
        return f"Outil inconnu : {name}"
    if not isinstance(data, dict):
        return "Les arguments doivent être un objet JSON."
    schema = spec["schema"]
    for key in schema["required"]:
        if key not in data:
            return f"Argument obligatoire manquant : {key}"
    for key, value in data.items():
        prop = schema["properties"].get(key)
        if prop is None:
            return f"Argument inconnu : {key}"
        expected = _TYPES[prop["type"]]
        if not isinstance(value, expected) or isinstance(value, bool):
            return f"L'argument {key} doit être de type {prop['type']}."
    return None


def _truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return f"{text[:half]}\n… [{len(text) - limit} caractères coupés] …\n{text[-half:]}"


class ToolExecutor:
    def __init__(self, root: Path, ui: UI, auto_approve: bool = False) -> None:
        self.root = root.resolve()
        self.ui = ui
        self.auto_approve = auto_approve
        self.always: set[str] = set()

    # --- utilitaires ----------------------------------------------------
    def resolve(self, path: str) -> Path:
        target = (self.root / (path or ".")).resolve()
        if target != self.root and self.root not in target.parents:
            raise ToolError(
                f"Accès refusé : « {path} » est en dehors du dossier de travail ({self.root})."
            )
        return target

    def rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.root)) or "."
        except ValueError:
            return str(path)

    def approve(self, tool: str) -> tuple[bool, str]:
        """Demande l'accord de l'utilisateur. Renvoie (accepté, remarque)."""
        if self.auto_approve or tool in self.always:
            return True, ""
        try:
            answer = self.ui.ask(
                "[bold]Autoriser ?[/] [green]o[/]ui / [red]n[/]on / [cyan]t[/]oujours pour "
                "ce type d'action › "
            ).strip().lower()
        except (EOFError, KeyboardInterrupt):
            return False, ""
        if answer in {"t", "toujours", "a", "always"}:
            self.always.add(tool)
            return True, ""
        if answer in {"o", "oui", "y", "yes", ""}:
            return True, ""
        try:
            why = self.ui.ask("[dim]Que doit faire NetIA à la place ? (Entrée pour passer) › [/]")
        except (EOFError, KeyboardInterrupt):
            why = ""
        return False, why.strip()

    # --- exécution -----------------------------------------------------
    def run(self, call: ToolCall) -> ToolResult:
        if call.input is None:
            self.ui.warn(f"Arguments invalides reçus pour {call.name}, l'IA va réessayer.")
            return ToolResult(call.id, json.dumps({"INVALID_JSON": call.raw}), True)
        error = validate(call.name, call.input)
        if error:
            self.ui.warn(f"{call.name} : {error}")
            return ToolResult(call.id, error, True)
        try:
            content = getattr(self, f"_{call.name}")(**call.input)
            return ToolResult(call.id, content)
        except ToolError as exc:
            self.ui.tool_result(str(exc), ok=False)
            return ToolResult(call.id, str(exc), True)
        except OSError as exc:
            msg = f"Erreur système : {exc}"
            self.ui.tool_result(msg, ok=False)
            return ToolResult(call.id, msg, True)

    def _declined(self, why: str) -> str:
        self.ui.tool_result("refusé par l'utilisateur", ok=False)
        msg = "L'utilisateur a refusé cette action."
        if why:
            msg += f" Sa consigne : {why}"
        raise ToolError(msg)

    def _list_directory(self, path: str = ".") -> str:
        target = self.resolve(path)
        self.ui.tool_header("Liste", self.rel(target))
        if not target.is_dir():
            raise ToolError(f"« {path} » n'est pas un dossier.")
        entries = []
        for child in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if child.is_dir():
                suffix = "/ (ignoré)" if child.name in SKIP_DIRS else "/"
                entries.append(child.name + suffix)
            else:
                entries.append(f"{child.name}  ({child.stat().st_size} o)")
        total = len(entries)
        entries = entries[:MAX_LIST_ENTRIES]
        if total > MAX_LIST_ENTRIES:
            entries.append(f"… et {total - MAX_LIST_ENTRIES} autres")
        self.ui.tool_result(f"{total} élément(s)")
        return "\n".join(entries) or "(dossier vide)"

    def _read_file(self, path: str) -> str:
        target = self.resolve(path)
        self.ui.tool_header("Lecture", self.rel(target))
        if not target.is_file():
            raise ToolError(f"Fichier introuvable : {path}")
        data = target.read_bytes()
        if b"\x00" in data[:4096]:
            raise ToolError("Fichier binaire : lecture impossible.")
        text = data[:MAX_READ_BYTES].decode("utf-8", errors="replace")
        note = f"\n… [fichier tronqué à {MAX_READ_BYTES} octets]" if len(data) > MAX_READ_BYTES else ""
        self.ui.tool_result(f"{text.count(chr(10)) + 1} lignes")
        return text + note

    def _create_directory(self, path: str) -> str:
        target = self.resolve(path)
        self.ui.tool_header("Dossier", self.rel(target))
        existed = target.is_dir()
        target.mkdir(parents=True, exist_ok=True)
        self.ui.tool_result("existait déjà" if existed else "créé")
        return f"Dossier {'déjà présent' if existed else 'créé'} : {self.rel(target)}"

    def _write_file(self, path: str, content: str) -> str:
        target = self.resolve(path)
        exists = target.is_file()
        self.ui.tool_header("Modifier" if exists else "Créer", self.rel(target))
        if exists:
            old = target.read_text(encoding="utf-8", errors="replace")
            self.ui.preview_diff(Path(self.rel(target)), old, content)
        else:
            self.ui.preview_file(Path(self.rel(target)), content)
        ok, why = self.approve("write_file")
        if not ok:
            self._declined(why)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
        lines = content.count("\n") + (0 if content.endswith("\n") or not content else 1)
        self.ui.tool_result(f"{'modifié' if exists else 'créé'} ({lines} lignes)")
        return f"Fichier {'remplacé' if exists else 'créé'} : {self.rel(target)} ({lines} lignes)"

    def _edit_file(self, path: str, old_text: str, new_text: str) -> str:
        target = self.resolve(path)
        self.ui.tool_header("Modifier", self.rel(target))
        if not target.is_file():
            raise ToolError(f"Fichier introuvable : {path}")
        old = target.read_text(encoding="utf-8", errors="replace")
        count = old.count(old_text) if old_text else 0
        if count == 0:
            raise ToolError("old_text introuvable dans le fichier : relis-le avec read_file.")
        if count > 1:
            raise ToolError(f"old_text apparaît {count} fois : ajoute du contexte pour qu'il soit unique.")
        new = old.replace(old_text, new_text, 1)
        self.ui.preview_diff(Path(self.rel(target)), old, new)
        ok, why = self.approve("edit_file")
        if not ok:
            self._declined(why)
        target.write_text(new, encoding="utf-8", newline="\n")
        self.ui.tool_result("modifié")
        return f"Fichier modifié : {self.rel(target)}"

    def _run_command(self, command: str, timeout: int = 120) -> str:
        timeout = max(1, min(int(timeout), 600))
        self.ui.tool_header("Commande", "")
        self.ui.preview_command(command)
        ok, why = self.approve("run_command")
        if not ok:
            self._declined(why)
        self.ui.waiting("Exécution…")
        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=self.root,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=timeout,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
        except subprocess.TimeoutExpired:
            self.ui.stop_waiting()
            raise ToolError(f"Commande arrêtée après {timeout} s (délai dépassé).")
        finally:
            self.ui.stop_waiting()
        output = (proc.stdout or "") + (("\n" + proc.stderr) if proc.stderr else "")
        output = output.strip()
        tail = "\n".join(output.splitlines()[-8:]) if output else "(aucune sortie)"
        self.ui.tool_result(f"code de retour {proc.returncode}\n{tail}", ok=proc.returncode == 0)
        return f"Code de retour : {proc.returncode}\n{_truncate(output) or '(aucune sortie)'}"
