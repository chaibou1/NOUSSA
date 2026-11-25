"""Boucle d'agent : l'IA répond, appelle des outils, voit les résultats, continue."""

from __future__ import annotations

from netia.backends import Backend, BackendError
from netia.tools import ToolExecutor
from netia.ui import UI

MAX_STEPS = 40


class Agent:
    def __init__(self, backend: Backend, executor: ToolExecutor, ui: UI) -> None:
        self.backend = backend
        self.executor = executor
        self.ui = ui
        self.transcript: list[tuple[str, str]] = []

    def send(self, text: str) -> str:
        """Envoie un message et exécute les outils demandés jusqu'à la réponse finale.

        En cas d'erreur ou d'interruption, l'historique revient à l'état d'avant
        ce message (les fichiers déjà écrits restent écrits).
        """
        checkpoint = self.backend.checkpoint()
        self.backend.add_user(text)
        answer: list[str] = []
        try:
            for _ in range(MAX_STEPS):
                reply, calls = self.backend.step(self.ui)
                if reply.strip():
                    answer.append(reply.strip())
                if not calls:
                    break
                results = [self.executor.run(call) for call in calls]
                self.backend.add_tool_results(results)
            else:
                self.ui.warn(f"Arrêt après {MAX_STEPS} étapes. Dis « continue » pour reprendre.")
        except (BackendError, KeyboardInterrupt):
            self.ui.stop_waiting()
            self.backend.rollback(checkpoint)
            raise
        full = "\n\n".join(answer)
        self.transcript.append((text, full))
        return full

    def reset(self) -> None:
        self.backend.reset()
        self.transcript.clear()
