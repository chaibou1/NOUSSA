"""Lecture / écriture de la configuration (clé API, modèle) de NetIA.

La configuration est stockée dans ~/.config/netia/config.json (ou dans
$NETIA_CONFIG_DIR si cette variable est définie), avec des droits 600 pour
que seule ton utilisateur puisse lire la clé.
"""

from __future__ import annotations

import getpass
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

DEFAULT_MODEL = "claude-opus-5-5"


def config_dir() -> Path:
    custom = os.environ.get("NETIA_CONFIG_DIR")
    if custom:
        return Path(custom)
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "netia"


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class Config:
    api_key: str = ""
    model: str = DEFAULT_MODEL

    @property
    def masked_key(self) -> str:
        if not self.api_key:
            return "(aucune)"
        if len(self.api_key) <= 12:
            return "****"
        return f"{self.api_key[:7]}…{self.api_key[-4:]}"


def load() -> Config:
    """Charge la config. La variable ANTHROPIC_API_KEY a priorité sur le fichier."""
    cfg = Config()
    path = config_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        cfg.api_key = data.get("api_key", "") or ""
        cfg.model = data.get("model", DEFAULT_MODEL) or DEFAULT_MODEL
    env_key = os.environ.get("ANTHROPIC_API_KEY")
    if env_key:
        cfg.api_key = env_key
    return cfg


def save(cfg: Config) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Crée le fichier avec des droits restreints avant d'y écrire la clé.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(asdict(cfg), fh, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows : chmod partiel, sans gravité
    return path


def reset() -> bool:
    path = config_path()
    if path.exists():
        path.unlink()
        return True
    return False


def prompt_for_key(cfg: Config | None = None) -> Config:
    """Demande la clé API de façon interactive (saisie masquée) et la sauvegarde."""
    cfg = cfg or load()
    print("🔑 Configuration de NetIA")
    print("   Crée une clé sur https://console.anthropic.com/settings/keys")
    print("   (la saisie est masquée, c'est normal que rien ne s'affiche)\n")
    while True:
        key = getpass.getpass("Clé API Anthropic : ").strip()
        if key:
            break
        print("La clé ne peut pas être vide.")
    model = input(f"Modèle [{cfg.model}] : ").strip()
    cfg.api_key = key
    if model:
        cfg.model = model
    path = save(cfg)
    print(f"\n✅ Configuration enregistrée dans {path}\n")
    return cfg
