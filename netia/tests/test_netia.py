import io
import os
import stat
from types import SimpleNamespace

import pytest

from netia import cli
from netia import config as cfgmod
from netia.assistant import Assistant, AssistantError, history_content
from netia.prompts import system_prompt


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("NETIA_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def block(type_, **kw):
    return SimpleNamespace(type=type_, **kw)


class FakeStream:
    def __init__(self, chunks, stop_reason="end_turn"):
        self.text_stream = iter(chunks)
        self._final = SimpleNamespace(
            stop_reason=stop_reason, content=[block("text", text="".join(chunks))]
        )

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._final


def fake_assistant(monkeypatch, chunks, stop_reason="end_turn"):
    a = Assistant(cfgmod.Config(api_key="sk-ant-test"), theme="cmd")
    calls = []

    def stream(**kwargs):
        calls.append(kwargs)
        return FakeStream(chunks, stop_reason)

    monkeypatch.setattr(a.client.beta.messages, "stream", stream)
    return a, calls


def test_save_and_load_config_with_private_permissions():
    path = cfgmod.save(cfgmod.Config(api_key="sk-ant-abcdefghijkl1234", model="m"))
    loaded = cfgmod.load()
    assert loaded.api_key == "sk-ant-abcdefghijkl1234"
    assert loaded.model == "m"
    assert loaded.masked_key == "sk-ant-…1234"
    if os.name == "posix":
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_env_key_overrides_file(monkeypatch):
    cfgmod.save(cfgmod.Config(api_key="from-file"))
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    assert cfgmod.load().api_key == "from-env"


def test_reset():
    cfgmod.save(cfgmod.Config(api_key="x"))
    assert cfgmod.reset() is True
    assert cfgmod.load().api_key == ""


def test_system_prompt_includes_theme_and_vendor():
    p = system_prompt("proto", "mikrotik")
    assert "PROTOCOLE" in p and "mikrotik" in p


def test_ask_streams_and_keeps_history(monkeypatch):
    a, calls = fake_assistant(monkeypatch, ["show ", "ip route"])
    out = io.StringIO()
    assert a.ask("table de routage ?", out=out) == "show ip route"
    assert "show ip route" in out.getvalue()
    req = calls[0]
    assert req["model"] == cfgmod.DEFAULT_MODEL
    assert req["fallbacks"] == "default"
    assert [m["role"] for m in a.messages] == ["user", "assistant"]


def test_refusal_is_reported_and_not_kept(monkeypatch):
    a, _ = fake_assistant(monkeypatch, [], stop_reason="refusal")
    with pytest.raises(AssistantError):
        a.ask("question", out=io.StringIO())
    assert a.messages == []


def test_history_content_drops_thinking_before_fallback():
    content = [
        block("thinking"),
        block("text", text="début"),
        block("fallback"),
        block("thinking"),
        block("text", text="suite"),
    ]
    kept = [b.type for b in history_content(content)]
    assert kept == ["text", "fallback", "thinking", "text"]


def test_missing_key_without_tty_fails_cleanly(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    assert cli.main(["ask", "bonjour"]) == 1
    assert "netia config" in capsys.readouterr().err


def test_config_show(capsys):
    cfgmod.save(cfgmod.Config(api_key="sk-ant-abcdefghijkl1234"))
    assert cli.main(["config", "--show"]) == 0
    out = capsys.readouterr().out
    assert "…1234" in out and "abcdefghijkl" not in out
