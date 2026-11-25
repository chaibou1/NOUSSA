"""Appels à l'API Claude (streaming, multi-tours, repli automatique)."""

from __future__ import annotations

import sys
from typing import Any, TextIO

import anthropic

from netia.config import Config
from netia.prompts import system_prompt

# Repli côté serveur : si le modèle principal refuse une requête (faux positif
# des filtres de sécurité, fréquent sur les sujets « sécurité réseau »), l'API
# relance automatiquement la même requête sur un autre modèle.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

# Blocs internes au modèle à ne pas renvoyer s'ils précèdent un bloc `fallback`.
_PRE_FALLBACK_DROP = {"thinking", "redacted_thinking", "tool_use", "server_tool_use"}


class AssistantError(Exception):
    """Erreur affichable telle quelle à l'utilisateur."""


def history_content(content: list[Any]) -> list[Any]:
    """Prépare le contenu d'une réponse pour l'historique de la conversation.

    Après un repli en cours de réponse, les blocs de réflexion situés avant le
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
        b
        for i, b in enumerate(content)
        if i >= last_fb or getattr(b, "type", None) not in _PRE_FALLBACK_DROP
    ]


class Assistant:
    def __init__(
        self,
        cfg: Config,
        theme: str = "general",
        vendor: str | None = None,
        effort: str = "medium",
    ) -> None:
        if not cfg.api_key:
            raise AssistantError("Aucune clé API configurée. Lance `netia config`.")
        self.client = anthropic.Anthropic(api_key=cfg.api_key)
        self.model = cfg.model
        self.effort = effort
        self.system = system_prompt(theme, vendor)
        self.messages: list[dict[str, Any]] = []

    def reset(self) -> None:
        self.messages.clear()

    def ask(self, question: str, out: TextIO = sys.stdout) -> str:
        """Envoie une question, affiche la réponse en direct et la renvoie."""
        self.messages.append({"role": "user", "content": question})
        try:
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=64000,
                system=self.system,
                messages=self.messages,
                output_config={"effort": self.effort},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            ) as stream:
                for text in stream.text_stream:
                    out.write(text)
                    out.flush()
                final = stream.get_final_message()
        except anthropic.AuthenticationError:
            self.messages.pop()
            raise AssistantError("Clé API invalide. Relance `netia config` pour la changer.")
        except anthropic.PermissionDeniedError:
            self.messages.pop()
            raise AssistantError("Accès refusé : ta clé n'a pas accès à ce modèle.")
        except anthropic.NotFoundError:
            self.messages.pop()
            raise AssistantError(
                f"Modèle introuvable : « {self.model} ». Change-le avec `netia config`."
            )
        except anthropic.RateLimitError:
            self.messages.pop()
            raise AssistantError("Trop de requêtes (ou crédit épuisé). Réessaie dans un moment.")
        except anthropic.APIConnectionError:
            self.messages.pop()
            raise AssistantError("Impossible de joindre l'API. Vérifie ta connexion Internet.")
        except anthropic.APIStatusError as exc:
            self.messages.pop()
            raise AssistantError(f"Erreur de l'API ({exc.status_code}) : {exc.message}")

        out.write("\n")
        if final.stop_reason == "refusal":
            self.messages.pop()
            raise AssistantError(
                "La demande a été refusée par les filtres de sécurité. "
                "Reformule-la (précise le contexte : TP, labo, ton propre réseau)."
            )
        if final.stop_reason == "max_tokens":
            out.write("\n[Réponse tronquée : trop longue.]\n")

        self.messages.append({"role": "assistant", "content": history_content(final.content)})
        return "".join(b.text for b in final.content if b.type == "text")
