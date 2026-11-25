"""Connexion aux fournisseurs d'IA.

Chaque backend garde l'historique de la conversation dans le format de son
API et expose la même interface :
    add_user(text) · step(ui) -> (texte, appels d'outils) · add_tool_results(results)
    checkpoint() / rollback(n) pour annuler un tour qui a échoué.
"""

from __future__ import annotations

import json
from typing import Any

from netia import providers
from netia.tools import TOOL_SPECS, ToolCall, ToolResult
from netia.ui import UI

MAX_TOKENS = 64000

# Repli côté serveur (Claude) : si le modèle refuse une requête à tort (faux
# positif des filtres, fréquent sur les sujets « sécurité réseau »), l'API
# relance automatiquement la même requête sur un autre modèle.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = {
    "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5",
    "claude-fable-5-2", "claude-fable-5-1",
}
EFFORT_PREFIXES = (
    "claude-opus-5", "claude-sonnet-5", "claude-haiku-5", "claude-fable", "claude-mythos",
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8", "claude-sonnet-4-6",
)
_PRE_FALLBACK_DROP = {"thinking", "redacted_thinking", "tool_use", "server_tool_use"}


class BackendError(Exception):
    """Erreur affichable telle quelle à l'utilisateur."""


def history_content(content: list[Any]) -> list[Any]:
    """Contenu d'une réponse Claude à renvoyer dans l'historique.

    Après un repli en cours de réponse, les blocs internes situés avant le
    dernier bloc `fallback` ne doivent pas être renvoyés ; le bloc `fallback`
    lui-même reste à sa place.
    """
    last_fb = max(
        (i for i, b in enumerate(content) if getattr(b, "type", None) == "fallback"),
        default=-1,
    )
    if last_fb < 0:
        return list(content)
    return [
        b for i, b in enumerate(content)
        if i >= last_fb or getattr(b, "type", None) not in _PRE_FALLBACK_DROP
    ]


class Backend:
    provider: providers.Provider

    def __init__(self, model: str, system: str, use_tools: bool = True, effort: str = "medium"):
        self.model = model
        self.system = system
        self.use_tools = use_tools
        self.effort = effort
        self.messages: list[dict[str, Any]] = []

    @property
    def label(self) -> str:
        return f"{self.provider.label} · {self.model}"

    def checkpoint(self) -> int:
        return len(self.messages)

    def rollback(self, n: int) -> None:
        del self.messages[n:]

    def reset(self) -> None:
        self.messages.clear()

    def add_user(self, text: str) -> None:
        self.messages.append({"role": "user", "content": text})

    def step(self, ui: UI) -> tuple[str, list[ToolCall]]:  # pragma: no cover - interface
        raise NotImplementedError

    def add_tool_results(self, results: list[ToolResult]) -> None:  # pragma: no cover
        raise NotImplementedError


# --- Claude (SDK Anthropic) -------------------------------------------------


class AnthropicBackend(Backend):
    provider = providers.get("anthropic")

    def __init__(self, api_key: str, model: str, system: str, use_tools: bool = True,
                 effort: str = "medium"):
        super().__init__(model, system, use_tools, effort)
        import anthropic

        self._sdk = anthropic
        self.client = anthropic.Anthropic(api_key=api_key)

    def _params(self) -> dict[str, Any]:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": MAX_TOKENS,
            "system": self.system,
            "messages": self.messages,
            "cache_control": {"type": "ephemeral"},
        }
        if self.use_tools:
            params["tools"] = [
                {
                    "name": s["name"],
                    "description": s["description"],
                    "input_schema": s["schema"],
                    "eager_input_streaming": True,
                }
                for s in TOOL_SPECS
            ]
        if self.model.startswith(EFFORT_PREFIXES):
            params["output_config"] = {"effort": self.effort}
        if self.model in FALLBACK_MODELS:
            params["betas"] = [FALLBACK_BETA]
            params["fallbacks"] = "default"
        return params

    def step(self, ui: UI) -> tuple[str, list[ToolCall]]:
        sdk = self._sdk
        final = None
        for _attempt in range(3):
            ui.waiting()
            try:
                with self.client.beta.messages.stream(**self._params()) as stream:
                    for event in stream:
                        if event.type == "text":
                            ui.text(event.text)
                        elif (event.type == "content_block_start"
                              and event.content_block.type == "tool_use"):
                            ui.flush()
                            ui.waiting(f"Préparation : {event.content_block.name}…")
                    final = stream.get_final_message()
                break
            except ValueError:
                # Arguments d'outil illisibles reçus en streaming : on relance.
                ui.warn("Réponse illisible reçue, nouvelle tentative…")
            except sdk.AuthenticationError:
                raise BackendError("Clé API Anthropic invalide. Lance `netia config`.")
            except sdk.PermissionDeniedError:
                raise BackendError("Accès refusé : ta clé n'a pas accès à ce modèle.")
            except sdk.NotFoundError:
                raise BackendError(f"Modèle introuvable : « {self.model} ».")
            except sdk.RateLimitError:
                raise BackendError("Trop de requêtes (ou crédit épuisé). Réessaie dans un moment.")
            except sdk.APIConnectionError:
                raise BackendError("Impossible de joindre l'API Anthropic. Vérifie ta connexion.")
            except sdk.APIStatusError as exc:
                raise BackendError(f"Erreur de l'API ({exc.status_code}) : {exc.message}")
            finally:
                ui.flush()
        if final is None:
            raise BackendError("Réponse illisible après 3 tentatives.")

        if final.stop_reason == "refusal":
            raise BackendError(
                "Demande refusée par les filtres de sécurité. Reformule en précisant le "
                "contexte (TP, labo, ton propre réseau)."
            )
        calls = [
            ToolCall(b.id, b.name, b.input if isinstance(b.input, dict) else None,
                     json.dumps(b.input, ensure_ascii=False, default=str))
            for b in final.content if b.type == "tool_use"
        ]
        if final.stop_reason == "max_tokens":
            if calls:
                raise BackendError("Réponse coupée (trop longue) avant la fin d'une action.")
            ui.warn("Réponse tronquée : trop longue.")
        self.messages.append({"role": "assistant", "content": history_content(final.content)})
        text = "".join(b.text for b in final.content if b.type == "text")
        return text, calls

    def add_tool_results(self, results: list[ToolResult]) -> None:
        self.messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": r.call_id, "content": r.content,
                 "is_error": r.is_error}
                for r in results
            ],
        })


# --- APIs compatibles OpenAI (OpenAI, Gemini, Mistral, DeepSeek, Groq, Ollama) ---


class OpenAICompatBackend(Backend):
    def __init__(self, provider: providers.Provider, api_key: str, model: str, system: str,
                 use_tools: bool = True, effort: str = "medium", base_url: str | None = None):
        super().__init__(model, system, use_tools, effort)
        try:
            import openai
        except ImportError:  # pragma: no cover
            raise BackendError("Le paquet `openai` est requis : pip install openai")
        self.provider = provider
        self._sdk = openai
        self.client = openai.OpenAI(
            api_key=api_key or "sans-cle", base_url=base_url or provider.base_url
        )

    def _all_messages(self) -> list[dict[str, Any]]:
        return [{"role": "system", "content": self.system}, *self.messages]

    def step(self, ui: UI) -> tuple[str, list[ToolCall]]:
        sdk = self._sdk
        params: dict[str, Any] = {
            "model": self.model, "messages": self._all_messages(), "stream": True,
        }
        if self.use_tools:
            params["tools"] = [
                {"type": "function", "function": {
                    "name": s["name"], "description": s["description"], "parameters": s["schema"],
                }}
                for s in TOOL_SPECS
            ]
        text = ""
        slots: dict[int, dict[str, str]] = {}
        finish = None
        ui.waiting()
        try:
            for chunk in self.client.chat.completions.create(**params):
                if not chunk.choices:
                    continue
                choice = chunk.choices[0]
                delta = choice.delta
                if delta.content:
                    text += delta.content
                    ui.text(delta.content)
                for tc in delta.tool_calls or []:
                    slot = slots.setdefault(tc.index, {"id": "", "name": "", "args": ""})
                    if tc.id:
                        slot["id"] = tc.id
                    if tc.function and tc.function.name:
                        if not slot["name"]:
                            ui.flush()
                            ui.waiting(f"Préparation : {tc.function.name}…")
                        slot["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        slot["args"] += tc.function.arguments
                finish = choice.finish_reason or finish
        except sdk.AuthenticationError:
            raise BackendError(f"Clé API {self.provider.label} invalide. Lance `netia config`.")
        except sdk.NotFoundError:
            raise BackendError(f"Modèle introuvable chez {self.provider.label} : « {self.model} ».")
        except sdk.RateLimitError:
            raise BackendError("Trop de requêtes (ou crédit épuisé). Réessaie dans un moment.")
        except sdk.APIConnectionError:
            hint = " Ollama est-il lancé ?" if self.provider.id == "ollama" else ""
            raise BackendError(f"Impossible de joindre {self.provider.label}.{hint}")
        except sdk.APIStatusError as exc:
            raise BackendError(f"Erreur de l'API ({exc.status_code}) : {exc.message}")
        finally:
            ui.flush()

        calls: list[ToolCall] = []
        msg: dict[str, Any] = {"role": "assistant", "content": text or None}
        if slots:
            msg["tool_calls"] = []
            for i in sorted(slots):
                s = slots[i]
                call_id = s["id"] or f"call_{i}"
                msg["tool_calls"].append({
                    "id": call_id, "type": "function",
                    "function": {"name": s["name"], "arguments": s["args"] or "{}"},
                })
                try:
                    args = json.loads(s["args"] or "{}")
                except json.JSONDecodeError:
                    args = None
                calls.append(ToolCall(call_id, s["name"], args if isinstance(args, dict) else None,
                                      s["args"]))
        if finish == "length":
            if calls:
                raise BackendError("Réponse coupée (trop longue) avant la fin d'une action.")
            ui.warn("Réponse tronquée : trop longue.")
        self.messages.append(msg)
        return text, calls

    def add_tool_results(self, results: list[ToolResult]) -> None:
        for r in results:
            content = f"ERREUR : {r.content}" if r.is_error else r.content
            self.messages.append({"role": "tool", "tool_call_id": r.call_id, "content": content})


def make_backend(cfg, provider_id: str, model: str, system: str, use_tools: bool = True,
                 effort: str = "medium") -> Backend:
    prov = providers.get(provider_id)
    key = cfg.key_for(provider_id)
    if prov.needs_key and not key:
        raise BackendError(f"Aucune clé API pour {prov.label}. Lance `netia config`.")
    if prov.kind == "anthropic":
        return AnthropicBackend(key, model, system, use_tools, effort)
    return OpenAICompatBackend(prov, key, model, system, use_tools, effort)
