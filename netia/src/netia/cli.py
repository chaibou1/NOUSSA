"""Interface en ligne de commande de NetIA.

Exemples :
    netia                              # agent conversationnel dans le terminal
    netia ask "crée un script Python qui ping 192.168.1.0/24"
    netia proto OSPF
    netia -p mistral cmd "voir la table de routage sous Linux"
    netia config                       # fournisseur, modèle, clé API
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.table import Table

from netia import __version__, providers
from netia import config as cfgmod
from netia.agent import Agent
from netia.backends import BackendError, make_backend
from netia.prompts import THEME_HELP, system_prompt
from netia.tools import ToolExecutor
from netia.ui import UI

HELP_CHAT = """\
[bold]Commandes :[/]
  /model [nom]        changer de modèle (sans nom : liste)
  /provider [nom]     changer de fournisseur d'IA (sans nom : liste)
  /theme [nom]        changer de thème (sans nom : liste)
  /vendor [nom]       constructeur / système (cisco, mikrotik, linux…)
  /auto               activer / désactiver la validation automatique des actions
  /save [fichier]     enregistrer la conversation en Markdown
  /reset              nouvelle conversation
  /aide               cette aide
  /quitter            quitter (ou Ctrl+D)"""


class Session:
    """État d'une session : config, modèle courant, agent."""

    def __init__(self, cfg: cfgmod.Config, ui: UI, provider: str, model: str, theme: str,
                 vendor: str | None, effort: str, use_tools: bool, auto: bool) -> None:
        self.cfg, self.ui = cfg, ui
        self.provider, self.model = provider, model
        self.theme, self.vendor, self.effort = theme, vendor, effort
        self.use_tools = use_tools
        self.root = Path.cwd()
        self.executor = ToolExecutor(self.root, ui, auto_approve=auto)
        self.agent = self._new_agent()

    def _new_agent(self) -> Agent:
        system = system_prompt(self.theme, self.vendor, self.root, self.use_tools)
        backend = make_backend(self.cfg, self.provider, self.model, system,
                               self.use_tools, self.effort)
        return Agent(backend, self.executor, self.ui)

    def rebuild(self) -> None:
        self.agent = self._new_agent()

    @property
    def label(self) -> str:
        return self.agent.backend.label


def ensure_key(cfg: cfgmod.Config, provider_id: str) -> cfgmod.Config:
    """Demande la clé du fournisseur si elle manque (premier lancement)."""
    if cfg.has_key(provider_id):
        return cfg
    prov = providers.get(provider_id)
    if not sys.stdin.isatty():
        raise BackendError(
            f"Aucune clé API pour {prov.label}. Lance `netia config` ou définis {prov.env_var}."
        )
    first = not cfgmod.config_path().exists()
    if first:
        print("👋 Première utilisation de NetIA.\n")
        return cfgmod.interactive_setup(cfg)
    cfg = cfgmod.prompt_key(cfg, provider_id)
    cfgmod.save(cfg)
    return cfg


def print_models(ui: UI, cfg: cfgmod.Config) -> None:
    table = Table(title="Fournisseurs et modèles", show_lines=False)
    table.add_column("Fournisseur (-p)")
    table.add_column("Modèles suggérés (-m)")
    table.add_column("Clé", justify="center")
    for p in providers.PROVIDERS.values():
        models = "\n".join(
            ("➜ " if (p.id == cfg.provider and m == cfg.model) else "  ") + m
            + (f"  [dim]{p.notes[m]}[/]" if m in p.notes else "")
            for m in p.models
        )
        key = "—" if not p.needs_key else ("✅" if cfg.has_key(p.id) else "❌")
        table.add_row(f"[bold]{p.id}[/]\n[dim]{p.label}[/]", models, key)
    ui.console.print(table)
    ui.console.print("[dim]Tu peux aussi saisir n'importe quel autre nom de modèle.[/]")


def print_themes(ui: UI) -> None:
    for name, desc in THEME_HELP.items():
        ui.console.print(f"  [bold]{name:<10}[/] {desc}")


def save_transcript(path: Path, transcript: list[tuple[str, str]]) -> None:
    parts = ["# Session NetIA\n"]
    for question, answer in transcript:
        parts.append(f"## ❓ {question}\n\n{answer}\n")
    path.write_text("\n".join(parts), encoding="utf-8")


def handle_slash(s: Session, line: str) -> bool:
    """Traite une commande /… Renvoie False pour quitter."""
    ui = s.ui
    cmd, _, arg = line[1:].partition(" ")
    arg = arg.strip()
    if cmd in {"quitter", "quit", "exit", "q"}:
        return False
    if cmd in {"aide", "help", "?"}:
        ui.console.print(HELP_CHAT)
    elif cmd == "reset":
        s.agent.reset()
        ui.info("Nouvelle conversation.")
    elif cmd == "model":
        if not arg:
            print_models(ui, s.cfg)
            return True
        s.model = arg
        s.agent.backend.model = arg  # même fournisseur : on garde la conversation
        ui.info(f"Modèle : {s.label}")
    elif cmd == "provider":
        if arg not in providers.PROVIDERS:
            print_models(ui, s.cfg)
            return True
        s.cfg = ensure_key(s.cfg, arg)
        s.provider, s.model = arg, providers.get(arg).default_model
        s.rebuild()
        ui.info(f"Fournisseur : {s.label} (nouvelle conversation)")
    elif cmd == "theme":
        if arg not in THEME_HELP:
            print_themes(ui)
            return True
        s.theme = arg
        s.rebuild()
        ui.info(f"Thème : {arg} (nouvelle conversation)")
    elif cmd == "vendor":
        s.vendor = arg or None
        s.rebuild()
        ui.info(f"Équipements : {s.vendor or 'non précisé'} (nouvelle conversation)")
    elif cmd == "auto":
        s.executor.auto_approve = not s.executor.auto_approve
        state = "activée ⚠️" if s.executor.auto_approve else "désactivée"
        ui.info(f"Validation automatique des actions {state}")
    elif cmd == "save":
        path = Path(arg or "netia-session.md")
        save_transcript(path, s.agent.transcript)
        ui.info(f"Conversation enregistrée dans {path}")
    else:
        ui.warn("Commande inconnue. Tape /aide.")
    return True


def run_chat(s: Session) -> int:
    ui = s.ui
    ui.console.print(
        f"[bold cyan]NetIA {__version__}[/] — ton agent réseau dans le terminal\n"
        f"[dim]{s.label} · dossier : {s.root}"
        + (f" · thème : {s.theme}" if s.theme != "general" else "")
        + (f" · {s.vendor}" if s.vendor else "")
        + "\nPose ta question ou demande-moi de créer quelque chose. /aide pour les commandes.[/]\n"
    )
    while True:
        try:
            line = ui.console.input("[bold green]❯ [/]").strip()
        except EOFError:
            ui.console.print("\nÀ bientôt !")
            return 0
        except KeyboardInterrupt:
            ui.console.print("\n[dim](Ctrl+D ou /quitter pour sortir)[/]")
            continue
        if not line:
            continue
        if line.startswith("/"):
            try:
                if not handle_slash(s, line):
                    ui.console.print("À bientôt !")
                    return 0
            except BackendError as exc:
                ui.error(str(exc))
            continue
        ui.console.print()
        try:
            s.agent.send(line)
        except BackendError as exc:
            ui.error(str(exc))
        except KeyboardInterrupt:
            ui.warn("Interrompu.")
        ui.console.print()


SHORTCUTS = {
    "cmd": ("cmd", "trouver une commande", "ce que tu veux faire"),
    "proto": ("proto", "expliquer un protocole", "nom du protocole (OSPF, STP, DHCP…)"),
    "configure": ("config", "configurer un équipement", "ce que tu veux configurer"),
    "python": ("python", "apprendre Python / automatisation réseau", "ta question"),
    "depannage": ("depannage", "diagnostiquer une panne", "description du problème"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netia",
        description="Agent IA dans le terminal pour les réseaux informatiques et le code : "
        "commandes, protocoles, configuration de routeurs/switches, création de fichiers.",
    )
    parser.add_argument("--version", action="version", version=f"netia {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-p", "--provider", choices=list(providers.PROVIDERS),
                        help="fournisseur d'IA pour cette fois (voir `netia models`)")
    common.add_argument("-m", "--model", help="modèle pour cette fois")
    common.add_argument("-v", "--vendor",
                        help="constructeur / système (cisco, mikrotik, juniper, linux, windows…)")
    common.add_argument("-e", "--effort", default="medium",
                        choices=["low", "medium", "high", "xhigh", "max"],
                        help="profondeur de réflexion (Claude uniquement, défaut : medium)")
    common.add_argument("-y", "--yes", action="store_true",
                        help="valider automatiquement les écritures et commandes (prudence !)")
    common.add_argument("--no-tools", action="store_true",
                        help="réponses texte uniquement, sans créer de fichiers")
    common.add_argument("-o", "--output", type=Path,
                        help="enregistrer la réponse dans un fichier (commandes à une question)")

    sub = parser.add_subparsers(dest="command")
    p_chat = sub.add_parser("chat", parents=[common], help="agent conversationnel (par défaut)")
    p_chat.add_argument("-t", "--theme", default="general", choices=list(THEME_HELP))
    p_ask = sub.add_parser("ask", parents=[common], help="une question / une tâche")
    p_ask.add_argument("question", nargs="+")
    p_ask.add_argument("-t", "--theme", default="general", choices=list(THEME_HELP))
    for name, (_theme, help_txt, arg_help) in SHORTCUTS.items():
        p = sub.add_parser(name, parents=[common], help=help_txt)
        p.add_argument("question", nargs="+", help=arg_help)

    p_cfg = sub.add_parser("config", help="choisir le fournisseur, le modèle, la clé API")
    g = p_cfg.add_mutually_exclusive_group()
    g.add_argument("--show", action="store_true", help="afficher la configuration actuelle")
    g.add_argument("--reset", action="store_true", help="supprimer la configuration")
    sub.add_parser("models", help="lister les fournisseurs et modèles")
    sub.add_parser("themes", help="lister les thèmes")
    return parser


COMMANDS = {"chat", "ask", "config", "models", "themes", *SHORTCUTS}


_VALUE_OPTS = {"-p", "--provider", "-m", "--model", "-v", "--vendor", "-e", "--effort",
               "-o", "--output", "-t", "--theme"}


def normalize_argv(argv: list[str]) -> list[str]:
    """Rend la sous-commande facultative.

    `netia` → chat · `netia -p mistral` → chat -p mistral ·
    `netia "ma question"` → ask "ma question" · `netia -p groq proto OSPF` → proto -p groq OSPF
    """
    if not argv or argv[0] in {"-h", "--help", "--version"}:
        return argv or ["chat"]
    # Cherche le premier argument qui n'est ni une option ni la valeur d'une option.
    i = 0
    while i < len(argv) and argv[i].startswith("-"):
        i += 2 if argv[i] in _VALUE_OPTS else 1
    if i >= len(argv):
        return ["chat", *argv]
    if argv[i] in COMMANDS:
        return [argv[i], *argv[:i], *argv[i + 1:]]
    return ["ask", *argv]


def main(argv: list[str] | None = None) -> int:
    argv = normalize_argv(list(sys.argv[1:] if argv is None else argv))
    args = build_parser().parse_args(argv)
    command = args.command
    ui = UI()

    try:
        if command == "config":
            if args.show:
                cfg = cfgmod.load()
                ui.console.print(f"Fichier     : {cfgmod.config_path()}")
                ui.console.print(f"Fournisseur : {providers.get(cfg.provider).label}")
                ui.console.print(f"Modèle      : {cfg.model}")
                for pid, prov in providers.PROVIDERS.items():
                    if prov.needs_key and cfg.key_for(pid):
                        ui.console.print(f"Clé {pid:<9}: {cfgmod.mask(cfg.key_for(pid))}")
            elif args.reset:
                ui.console.print("Configuration supprimée." if cfgmod.reset() else "Aucune configuration.")
            else:
                cfgmod.interactive_setup()
            return 0
        if command == "models":
            print_models(ui, cfgmod.load())
            return 0
        if command == "themes":
            print_themes(ui)
            return 0

        cfg = cfgmod.load()
        provider = args.provider or cfg.provider
        cfg = ensure_key(cfg, provider)
        if not args.provider:
            provider = cfg.provider  # l'assistant de 1re config a pu le changer
        if args.model:
            model = args.model
        elif provider == cfg.provider:
            model = cfg.model
        else:
            model = providers.get(provider).default_model

        theme = SHORTCUTS[command][0] if command in SHORTCUTS else getattr(args, "theme", "general")
        session = Session(cfg, ui, provider, model, theme, args.vendor, args.effort,
                          use_tools=not args.no_tools, auto=args.yes)

        if command == "chat":
            return run_chat(session)

        question = " ".join(args.question)
        if command == "proto":
            question = f"Explique le protocole {question}."
        ui.console.print(f"[dim]{session.label}[/]\n")
        answer = session.agent.send(question)
        if args.output:
            args.output.write_text(f"# {question}\n\n{answer}\n", encoding="utf-8")
            ui.info(f"📄 Réponse enregistrée dans {args.output}")
        return 0
    except BackendError as exc:
        ui.error(str(exc))
        return 1
    except KeyboardInterrupt:
        ui.warn("Interrompu.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
