"""Interface en ligne de commande de NetIA.

Exemples :
    netia                              # mode conversation
    netia ask "configurer un VLAN 10 sur un switch Cisco"
    netia proto OSPF
    netia cmd "voir la table de routage sous Linux"
    netia config                       # (re)saisir la clé API
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from netia import __version__
from netia import config as cfgmod
from netia.assistant import Assistant, AssistantError
from netia.prompts import THEME_HELP

BANNER = f"""\
=== NetIA {__version__} — ton assistant réseau ===
Commandes : /theme <nom>  /vendor <nom>  /save <fichier>  /reset  /aide  /quitter
"""


def ensure_config() -> cfgmod.Config:
    cfg = cfgmod.load()
    if cfg.api_key:
        return cfg
    if not sys.stdin.isatty():
        raise AssistantError(
            "Aucune clé API. Lance `netia config` ou définis ANTHROPIC_API_KEY."
        )
    print("Première utilisation : NetIA a besoin de ta clé API.\n")
    return cfgmod.prompt_for_key(cfg)


def print_themes() -> None:
    print("Thèmes disponibles :")
    for name, desc in THEME_HELP.items():
        print(f"  {name:<10} {desc}")


def run_chat(assistant: Assistant, theme: str, vendor: str | None, effort: str) -> int:
    print(BANNER)
    print(f"Thème : {theme}" + (f" · Équipements : {vendor}" if vendor else ""))
    print()
    transcript: list[tuple[str, str]] = []
    while True:
        try:
            line = input("toi › ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nÀ bientôt !")
            return 0
        if not line:
            continue

        if line.startswith("/"):
            cmd, _, arg = line[1:].partition(" ")
            arg = arg.strip()
            if cmd in {"quitter", "quit", "exit", "q"}:
                print("À bientôt !")
                return 0
            if cmd in {"aide", "help"}:
                print(BANNER)
                print_themes()
            elif cmd == "reset":
                assistant.reset()
                transcript.clear()
                print("Conversation effacée.")
            elif cmd == "theme":
                if arg not in THEME_HELP:
                    print_themes()
                    continue
                theme = arg
                assistant = Assistant(cfgmod.load(), theme, vendor, effort)
                transcript.clear()
                print(f"Thème changé : {theme} (nouvelle conversation)")
            elif cmd == "vendor":
                vendor = arg or None
                assistant = Assistant(cfgmod.load(), theme, vendor, effort)
                transcript.clear()
                print(f"Équipements : {vendor or 'non précisé'} (nouvelle conversation)")
            elif cmd == "save":
                path = Path(arg or "netia-session.md")
                save_transcript(path, transcript)
                print(f"Conversation enregistrée dans {path}")
            else:
                print("Commande inconnue. Tape /aide.")
            continue

        print("\nnetia › ", end="", flush=True)
        try:
            answer = assistant.ask(line)
        except AssistantError as exc:
            print(f"\n⚠️  {exc}\n")
            continue
        except KeyboardInterrupt:
            print("\n[interrompu]\n")
            continue
        transcript.append((line, answer))
        print()


def save_transcript(path: Path, transcript: list[tuple[str, str]]) -> None:
    parts = ["# Session NetIA\n"]
    for question, answer in transcript:
        parts.append(f"## ❓ {question}\n\n{answer}\n")
    path.write_text("\n".join(parts), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="netia",
        description="Assistant IA pour les réseaux informatiques (commandes, protocoles, "
        "configuration de routeurs/switches, Python).",
    )
    parser.add_argument("--version", action="version", version=f"netia {__version__}")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "-v", "--vendor",
        help="constructeur / système (ex. cisco, mikrotik, juniper, linux, windows)",
    )
    common.add_argument(
        "-e", "--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
        help="profondeur de réflexion de l'IA (défaut : medium)",
    )
    common.add_argument("-o", "--output", type=Path, help="enregistrer la réponse dans un fichier")

    sub = parser.add_subparsers(dest="command")

    p_chat = sub.add_parser("chat", parents=[common], help="mode conversation (par défaut)")
    p_chat.add_argument("-t", "--theme", default="general", choices=list(THEME_HELP))

    p_ask = sub.add_parser("ask", parents=[common], help="poser une question")
    p_ask.add_argument("question", nargs="+")
    p_ask.add_argument("-t", "--theme", default="general", choices=list(THEME_HELP))

    shortcuts = {
        "cmd": ("trouver une commande", "ce que tu veux faire"),
        "proto": ("expliquer un protocole", "nom du protocole (OSPF, STP, DHCP…)"),
        "configure": ("configurer un équipement", "ce que tu veux configurer"),
        "python": ("apprendre Python / automatisation réseau", "ta question"),
        "depannage": ("diagnostiquer une panne", "description du problème"),
    }
    for name, (help_txt, arg_help) in shortcuts.items():
        p = sub.add_parser(name, parents=[common], help=help_txt)
        p.add_argument("question", nargs="+", help=arg_help)

    p_cfg = sub.add_parser("config", help="configurer la clé API et le modèle")
    g = p_cfg.add_mutually_exclusive_group()
    g.add_argument("--show", action="store_true", help="afficher la configuration actuelle")
    g.add_argument("--reset", action="store_true", help="supprimer la configuration")

    sub.add_parser("themes", help="lister les thèmes")
    return parser


SHORTCUT_THEMES = {
    "cmd": "cmd",
    "proto": "proto",
    "configure": "config",
    "python": "python",
    "depannage": "depannage",
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    command = args.command or "chat"

    try:
        if command == "config":
            if args.show:
                cfg = cfgmod.load()
                print(f"Fichier : {cfgmod.config_path()}")
                print(f"Clé API : {cfg.masked_key}")
                print(f"Modèle  : {cfg.model}")
            elif args.reset:
                print("Configuration supprimée." if cfgmod.reset() else "Aucune configuration.")
            else:
                cfgmod.prompt_for_key()
            return 0

        if command == "themes":
            print_themes()
            return 0

        cfg = ensure_config()
        vendor = getattr(args, "vendor", None)
        effort = getattr(args, "effort", "medium")

        if command == "chat":
            return run_chat(Assistant(cfg, args.theme, vendor, effort), args.theme, vendor, effort)

        theme = SHORTCUT_THEMES.get(command, getattr(args, "theme", "general"))
        question = " ".join(args.question)
        if command == "proto":
            question = f"Explique le protocole {question}."
        answer = Assistant(cfg, theme, vendor, effort).ask(question)
        if args.output:
            args.output.write_text(f"# {question}\n\n{answer}\n", encoding="utf-8")
            print(f"\n📄 Réponse enregistrée dans {args.output}")
        return 0
    except AssistantError as exc:
        print(f"⚠️  {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrompu.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
