import io
import json
import os
import stat
import sys
from types import SimpleNamespace as NS

import pytest
from rich.console import Console

from netia import cli
from netia import config as cfgmod
from netia.agent import Agent
from netia.backends import (
    AnthropicBackend, Backend, BackendError, OpenAICompatBackend, history_content,
)
from netia import providers
from netia.prompts import system_prompt
from netia.tools import ToolCall, ToolExecutor, ToolResult, validate
from netia.ui import UI, split_ready


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("NETIA_CONFIG_DIR", str(tmp_path / "cfg"))
    for p in providers.PROVIDERS.values():
        if p.env_var:
            monkeypatch.delenv(p.env_var, raising=False)


@pytest.fixture
def ui():
    return UI(Console(file=io.StringIO(), force_terminal=False, width=100))


def output(ui):
    return ui.console.file.getvalue()


# --- config -------------------------------------------------------------------


def test_save_and_load_config_with_private_permissions():
    path = cfgmod.save(cfgmod.Config("mistral", "mistral-large-latest", {"mistral": "k" * 20}))
    cfg = cfgmod.load()
    assert (cfg.provider, cfg.model, cfg.key_for("mistral")) == (
        "mistral", "mistral-large-latest", "k" * 20)
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_old_config_format_is_migrated():
    cfgmod.config_path().parent.mkdir(parents=True)
    cfgmod.config_path().write_text(json.dumps({"api_key": "sk-old", "model": "claude-opus-5-5"}))
    cfg = cfgmod.load()
    assert cfg.provider == "anthropic" and cfg.key_for("anthropic") == "sk-old"


def test_env_key_overrides_file(monkeypatch):
    cfgmod.save(cfgmod.Config(keys={"openai": "from-file"}))
    monkeypatch.setenv("OPENAI_API_KEY", "from-env")
    assert cfgmod.load().key_for("openai") == "from-env"


def test_ollama_needs_no_key():
    assert cfgmod.Config().has_key("ollama")
    assert not cfgmod.Config().has_key("groq")


# --- prompts / ui / validation --------------------------------------------------


def test_system_prompt_mentions_tools_theme_vendor(tmp_path):
    p = system_prompt("proto", "mikrotik", tmp_path)
    assert "PROTOCOLE" in p and "mikrotik" in p and str(tmp_path) in p and "outils" in p
    assert "Outils désactivés" in system_prompt(tools=False)


def test_split_ready_never_cuts_inside_code_block():
    ready, rest = split_ready("Intro\n\n```bash\nls\n\npwd\n")
    assert ready == "Intro\n\n" and rest.startswith("```bash")
    ready, rest = split_ready("```bash\nls\n```\nSuite")
    assert ready == "```bash\nls\n```\n" and rest == "Suite"


def test_validate():
    assert validate("write_file", {"path": "a"}) == "Argument obligatoire manquant : content"
    assert validate("run_command", {"command": "ls", "timeout": "5"})
    assert validate("read_file", {"path": "a", "x": 1}) == "Argument inconnu : x"
    assert validate("nope", {}) == "Outil inconnu : nope"
    assert validate("list_directory", {}) is None


# --- outils --------------------------------------------------------------------


def test_write_edit_read_in_workspace(tmp_path, ui):
    ex = ToolExecutor(tmp_path, ui, auto_approve=True)
    r = ex.run(ToolCall("1", "write_file", {"path": "projet/main.py", "content": "print('a')\n"}))
    assert not r.is_error and (tmp_path / "projet/main.py").read_text() == "print('a')\n"
    r = ex.run(ToolCall("2", "edit_file", {"path": "projet/main.py", "old_text": "'a'",
                                           "new_text": "'b'"}))
    assert not r.is_error
    assert "print('b')" in ex.run(ToolCall("3", "read_file", {"path": "projet/main.py"})).content
    assert "main.py" in ex.run(ToolCall("4", "list_directory", {"path": "projet"})).content
    assert not ex.run(ToolCall("5", "create_directory", {"path": "a/b/c"})).is_error
    assert (tmp_path / "a/b/c").is_dir()


def test_paths_outside_workspace_are_refused(tmp_path, ui):
    ex = ToolExecutor(tmp_path / "w", ui, auto_approve=True)
    (tmp_path / "w").mkdir()
    r = ex.run(ToolCall("1", "write_file", {"path": "../evil.txt", "content": "x"}))
    assert r.is_error and "en dehors" in r.content
    assert not (tmp_path / "evil.txt").exists()


def test_edit_requires_unique_match(tmp_path, ui):
    (tmp_path / "f.txt").write_text("a a")
    ex = ToolExecutor(tmp_path, ui, auto_approve=True)
    r = ex.run(ToolCall("1", "edit_file", {"path": "f.txt", "old_text": "a", "new_text": "b"}))
    assert r.is_error and "2 fois" in r.content


def test_user_can_decline_and_give_instructions(tmp_path, ui, monkeypatch):
    answers = iter(["n", "mets-le dans src/"])
    monkeypatch.setattr(ui, "ask", lambda prompt: next(answers))
    ex = ToolExecutor(tmp_path, ui)
    r = ex.run(ToolCall("1", "write_file", {"path": "a.py", "content": "x"}))
    assert r.is_error and "mets-le dans src/" in r.content
    assert not (tmp_path / "a.py").exists()


def test_always_answer_skips_next_confirmations(tmp_path, ui, monkeypatch):
    answers = iter(["t"])
    monkeypatch.setattr(ui, "ask", lambda prompt: next(answers))
    ex = ToolExecutor(tmp_path, ui)
    for i in range(2):
        assert not ex.run(ToolCall(str(i), "write_file", {"path": f"{i}.txt", "content": ""})).is_error


def test_run_command(tmp_path, ui):
    ex = ToolExecutor(tmp_path, ui, auto_approve=True)
    r = ex.run(ToolCall("1", "run_command", {"command": f'"{sys.executable}" -c "print(6*7)"'}))
    assert "Code de retour : 0" in r.content and "42" in r.content


def test_invalid_json_is_reported_to_model(tmp_path, ui):
    r = ToolExecutor(tmp_path, ui).run(ToolCall("1", "write_file", None, '{"path": "a'))
    assert r.is_error and "INVALID_JSON" in r.content


# --- boucle d'agent ------------------------------------------------------------


class ScriptedBackend(Backend):
    provider = providers.get("anthropic")

    def __init__(self, steps):
        super().__init__("m", "sys")
        self.steps = list(steps)
        self.results = []

    def step(self, ui):
        item = self.steps.pop(0)
        if isinstance(item, Exception):
            raise item
        self.messages.append({"role": "assistant", "content": item[0]})
        return item

    def add_tool_results(self, results):
        self.results.append(results)
        self.messages.append({"role": "user", "content": "results"})


def test_agent_runs_tools_until_final_answer(tmp_path, ui):
    backend = ScriptedBackend([
        ("Je crée le fichier.", [ToolCall("t1", "create_directory", {"path": "lab"})]),
        ("C'est fait.", []),
    ])
    agent = Agent(backend, ToolExecutor(tmp_path, ui), ui)
    assert agent.send("crée un dossier lab") == "Je crée le fichier.\n\nC'est fait."
    assert (tmp_path / "lab").is_dir()
    assert backend.results[0][0].call_id == "t1"


def test_agent_rolls_back_history_on_error(tmp_path, ui):
    backend = ScriptedBackend([("ok", []), BackendError("boom")])
    agent = Agent(backend, ToolExecutor(tmp_path, ui), ui)
    agent.send("premier")
    before = list(backend.messages)
    with pytest.raises(BackendError):
        agent.send("second")
    assert backend.messages == before


# --- backends ------------------------------------------------------------------


def block(type_, **kw):
    return NS(type=type_, **kw)


class FakeAnthropicStream:
    def __init__(self, events, final):
        self.events, self.final = events, final

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __iter__(self):
        return iter(self.events)

    def get_final_message(self):
        return self.final


def test_anthropic_backend_streams_text_and_returns_tool_calls(ui, monkeypatch):
    b = AnthropicBackend("sk-test", "claude-opus-5-5", "sys")
    calls = []
    tool = block("tool_use", id="toolu_1", name="read_file", input={"path": "a.txt"})
    final = NS(stop_reason="tool_use", content=[block("text", text="Je lis."), tool])

    def stream(**kw):
        calls.append(kw)
        return FakeAnthropicStream([NS(type="text", text="Je lis.")], final)

    monkeypatch.setattr(b.client.beta.messages, "stream", stream)
    b.add_user("lis a.txt")
    text, tool_calls = b.step(ui)
    assert text == "Je lis." and tool_calls[0].input == {"path": "a.txt"}
    req = calls[0]
    assert req["fallbacks"] == "default"
    assert all(t["eager_input_streaming"] for t in req["tools"])
    assert "Je lis." in output(ui)
    b.add_tool_results([ToolResult("toolu_1", "contenu")])
    assert b.messages[-1]["content"][0]["tool_use_id"] == "toolu_1"


def test_haiku_has_no_server_fallback():
    params = AnthropicBackend("sk", "claude-haiku-5-5", "sys")._params()
    assert "fallbacks" not in params and params["output_config"] == {"effort": "medium"}


def test_anthropic_refusal_raises(ui, monkeypatch):
    b = AnthropicBackend("sk-test", "claude-opus-5-5", "sys")
    final = NS(stop_reason="refusal", content=[])
    monkeypatch.setattr(b.client.beta.messages, "stream",
                        lambda **kw: FakeAnthropicStream([], final))
    b.add_user("x")
    with pytest.raises(BackendError):
        b.step(ui)


def test_history_content_drops_thinking_before_fallback():
    content = [block("thinking"), block("text", text="a"), block("fallback"),
               block("thinking"), block("text", text="b")]
    assert [b.type for b in history_content(content)] == ["text", "fallback", "thinking", "text"]


def chunk(content=None, tool_calls=None, finish=None):
    return NS(choices=[NS(delta=NS(content=content, tool_calls=tool_calls), finish_reason=finish)])


def tc(index, id=None, name=None, args=None):
    return NS(index=index, id=id, function=NS(name=name, arguments=args))


def test_openai_backend_accumulates_streamed_tool_calls(ui, monkeypatch):
    b = OpenAICompatBackend(providers.get("mistral"), "k", "mistral-large-latest", "sys")
    chunks = [
        chunk("Je crée "), chunk("le dossier."),
        chunk(tool_calls=[tc(0, "c1", "create_directory", '{"pa')]),
        chunk(tool_calls=[tc(0, args='th": "lab"}')], finish="tool_calls"),
    ]
    seen = {}

    def create(**kw):
        seen.update(kw)
        return iter(chunks)

    monkeypatch.setattr(b.client.chat.completions, "create", create)
    b.add_user("crée lab")
    text, calls = b.step(ui)
    assert text == "Je crée le dossier."
    assert calls[0].name == "create_directory" and calls[0].input == {"path": "lab"}
    assert seen["messages"][0] == {"role": "system", "content": "sys"}
    assert b.messages[-1]["tool_calls"][0]["function"]["arguments"] == '{"path": "lab"}'
    b.add_tool_results([ToolResult("c1", "ok")])
    assert b.messages[-1] == {"role": "tool", "tool_call_id": "c1", "content": "ok"}


# --- cli -----------------------------------------------------------------------


@pytest.mark.parametrize("argv, expected", [
    ([], ["chat"]),
    (["-p", "mistral"], ["chat", "-p", "mistral"]),
    (["comment", "faire"], ["ask", "comment", "faire"]),
    (["-p", "groq", "proto", "OSPF"], ["proto", "-p", "groq", "OSPF"]),
    (["-y", "crée", "un", "script"], ["ask", "-y", "crée", "un", "script"]),
    (["config", "--show"], ["config", "--show"]),
])
def test_normalize_argv(argv, expected):
    assert cli.normalize_argv(argv) == expected


def test_missing_key_without_tty_fails_cleanly(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert cli.main(["ask", "bonjour"]) == 1
    assert "netia config" in capsys.readouterr().out


def test_config_show_masks_keys(capsys):
    cfgmod.save(cfgmod.Config(keys={"anthropic": "sk-ant-abcdefghijkl1234"}))
    assert cli.main(["config", "--show"]) == 0
    out = capsys.readouterr().out
    assert "…1234" in out and "abcdefghijkl" not in out
