"""Lecture / écriture de la configuration de NetIA (fournisseur, modèle, clés API).

La configuration est stockée dans ~/.config/netia/config.json (ou dans
$NETIA_CONFIG_DIR si cette variable est définie), avec des droits 600 pour
que seul ton utilisateur puisse lire les clés.
"""

from __future__ import annotations

import getpass
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from netia import providers

DEFAULT_MODEL = providers.PROVIDERS[providers.DEFAULT_PROVIDER].default_model


def config_dir() -> Path:
    custom = os.environ.get("NETIA_CONFIG_DIR")
    if custom:
        return Path(custom)
    base = os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return Path(base) / "netia"


def config_path() -> Path:
    return config_dir() / "config.json"


def mask(key: str) -> str:
    if not key:
        return "(aucune)"
    if len(key) <= 12:
        return "****"
    return f"{key[:7]}…{key[-4:]}"


@dataclass
class Config:
    provider: str = providers.DEFAULT_PROVIDER
    model: str = DEFAULT_MODEL
    keys: dict[str, str] = field(default_factory=dict)

    def key_for(self, provider_id: str) -> str:
        """Clé du fournisseur : la variable d'environnement a priorité sur le fichier."""
        prov = providers.get(provider_id)
        if prov.env_var and os.environ.get(prov.env_var):
            return os.environ[prov.env_var]
        return self.keys.get(provider_id, "")

    def has_key(self, provider_id: str) -> bool:
        return not providers.get(provider_id).needs_key or bool(self.key_for(provider_id))


def load() -> Config:
    cfg = Config()
    path = config_path()
    if not path.exists():
        return cfg
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return cfg
    keys = dict(data.get("keys") or {})
    if data.get("api_key") and "anthropic" not in keys:  # ancien format (v0.1)
        keys["anthropic"] = data["api_key"]
    provider = data.get("provider") or providers.DEFAULT_PROVIDER
    if provider not in providers.PROVIDERS:
        provider = providers.DEFAULT_PROVIDER
    cfg.provider = provider
    cfg.model = data.get("model") or providers.get(provider).default_model
    cfg.keys = {k: v for k, v in keys.items() if v}
    return cfg


def save(cfg: Config) -> Path:
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Crée le fichier avec des droits restreints avant d'y écrire les clés.
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


# --- Saisie interactive -----------------------------------------------------


def _choose(title: str, options: list[tuple[str, str]], current: str | None,
            allow_other: bool = True) -> str | None:
    """Menu numéroté. Renvoie la valeur choisie, `None` pour « autre »."""
    print(title)
    for i, (value, desc) in enumerate(options, 1):
        mark = " ← actuel" if value == current else ""
        print(f"  {i}. {value:<24} {desc}{mark}")
    extra = 1 if allow_other else 0
    if allow_other:
        print(f"  {len(options) + 1}. autre (saisir un nom)")
    while True:
        raw = input(f"Choix [Entrée = {current or 1}] : ").strip()
        if not raw:
            return current or options[0][0]
        if raw.isdigit() and 1 <= int(raw) <= len(options) + extra:
            idx = int(raw) - 1
            return options[idx][0] if idx < len(options) else None
        for value, _ in options:
            if raw == value:
                return value
        print("Choix invalide.")


def prompt_key(cfg: Config, provider_id: str) -> Config:
    """Demande (saisie masquée) et enregistre la clé API d'un fournisseur."""
    prov = providers.get(provider_id)
    if not prov.needs_key:
        return cfg
    existing = cfg.keys.get(provider_id, "")
    print(f"\n🔑 Clé API {prov.label}")
    if prov.key_url:
        print(f"   À créer sur {prov.key_url}")
    print("   (la saisie est masquée, c'est normal que rien ne s'affiche)")
    while True:
        hint = f" [Entrée = garder {mask(existing)}]" if existing else ""
        key = getpass.getpass(f"Clé{hint} : ").strip()
        if key or existing:
            break
        print("La clé ne peut pas être vide.")
    if key:
        cfg.keys[provider_id] = key
    return cfg


def interactive_setup(cfg: Config | None = None) -> Config:
    """Assistant de configuration : fournisseur → modèle → clé API."""
    cfg = cfg or load()
    print("⚙️  Configuration de NetIA\n")
    prov_id = _choose(
        "Fournisseur d'IA :",
        [(p.id, p.label) for p in providers.PROVIDERS.values()],
        cfg.provider,
        allow_other=False,
    )
    prov = providers.get(prov_id)

    current_model = cfg.model if prov_id == cfg.provider else prov.default_model
    model = _choose(
        f"\nModèle {prov.label} :",
        [(m, prov.notes.get(m, "")) for m in prov.models],
        current_model if current_model in prov.models else None,
    )
    while not model:
        model = input("Nom exact du modèle : ").strip()

    cfg.provider, cfg.model = prov_id, model
    cfg = prompt_key(cfg, prov_id)
    path = save(cfg)
    print(f"\n✅ {prov.label} · {model} — configuration enregistrée dans {path}\n")
    return cfg
