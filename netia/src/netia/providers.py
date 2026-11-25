"""Catalogue des fournisseurs d'IA et des modèles proposés.

- « anthropic » utilise le SDK officiel Anthropic (Claude).
- Les autres utilisent le SDK OpenAI, car ils exposent une API compatible
  OpenAI (OpenAI, Google Gemini, Mistral, DeepSeek, Groq, Ollama en local).

Les listes de modèles ne sont que des suggestions : tu peux toujours saisir un
autre nom de modèle avec `netia config` ou `--model`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Provider:
    id: str
    label: str
    kind: str  # "anthropic" ou "openai"
    env_var: str | None
    base_url: str | None
    models: tuple[str, ...]
    key_url: str | None = None
    notes: dict[str, str] = field(default_factory=dict)

    @property
    def needs_key(self) -> bool:
        return self.env_var is not None

    @property
    def default_model(self) -> str:
        return self.models[0]


PROVIDERS: dict[str, Provider] = {
    p.id: p
    for p in [
        Provider(
            "anthropic", "Claude (Anthropic)", "anthropic", "ANTHROPIC_API_KEY", None,
            ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-2"),
            "https://console.anthropic.com/settings/keys",
            {
                "claude-opus-5-5": "polyvalent et très bon en code (défaut)",
                "claude-sonnet-5-5": "rapide, 2x moins cher qu'Opus",
                "claude-haiku-5-5": "très rapide, très bon marché",
                "claude-fable-5-2": "le plus puissant, le plus cher",
            },
        ),
        Provider(
            "openai", "OpenAI (ChatGPT)", "openai", "OPENAI_API_KEY", None,
            ("gpt-5", "gpt-5-mini"),
            "https://platform.openai.com/api-keys",
        ),
        Provider(
            "gemini", "Google Gemini", "openai", "GEMINI_API_KEY",
            "https://generativelanguage.googleapis.com/v1beta/openai/",
            ("gemini-2.5-pro", "gemini-2.5-flash"),
            "https://aistudio.google.com/apikey",
        ),
        Provider(
            "mistral", "Mistral AI", "openai", "MISTRAL_API_KEY",
            "https://api.mistral.ai/v1",
            ("mistral-large-latest", "codestral-latest"),
            "https://console.mistral.ai/api-keys",
        ),
        Provider(
            "deepseek", "DeepSeek", "openai", "DEEPSEEK_API_KEY",
            "https://api.deepseek.com",
            ("deepseek-chat",),
            "https://platform.deepseek.com/api_keys",
        ),
        Provider(
            "groq", "Groq (Llama…)", "openai", "GROQ_API_KEY",
            "https://api.groq.com/openai/v1",
            ("llama-3.3-70b-versatile",),
            "https://console.groq.com/keys",
        ),
        Provider(
            "ollama", "Ollama (local, gratuit)", "openai", None,
            "http://localhost:11434/v1",
            ("llama3.1", "qwen2.5-coder"),
            None,
            {"llama3.1": "il faut avoir lancé `ollama pull llama3.1`"},
        ),
    ]
}

DEFAULT_PROVIDER = "anthropic"


def get(provider_id: str) -> Provider:
    try:
        return PROVIDERS[provider_id]
    except KeyError:
        raise KeyError(
            f"Fournisseur inconnu : « {provider_id} ». Choix : {', '.join(PROVIDERS)}"
        ) from None
