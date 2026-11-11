"""P20: pipeline/peek.py — 출력 전에 .env 값을 가린다 (가짜 .env만 사용)."""
import urllib.parse

import pytest

from pipeline import peek

FAKE_A = "ABCDEF12-3456-7890-ABCD-EF1234567890"     # 가짜 값 (실제 키 아님)
FAKE_B = "s3cr3t+key/with=chars"                     # URL 인코딩하면 모양이 바뀌는 가짜 값


@pytest.fixture
def env_file(tmp_path):
    p = tmp_path / ".env"
    p.write_text(f"# 주석\nVITE_FAKE_KEY={FAKE_A}\nSERVER_FAKE_KEY=\"{FAKE_A}\"\nOTHER_FAKE={FAKE_B}\nSHORT=abc\n"
                 "EMPTY=\n", encoding="utf-8")
    return p


def _left_prefix(out: str, value: str) -> bool:
    return value[:6] in out


def test_masks_raw_and_url_encoded(env_file):
    env = peek.read_env(env_file)
    text = (f'const env = {{"VITE_FAKE_KEY": "{FAKE_A}"}}\n'
            f"tile https://x/{FAKE_A}/a.png\n"
            f"q={urllib.parse.quote(FAKE_B, safe='')}&p={urllib.parse.quote_plus(FAKE_B)}&raw={FAKE_B}\n")
    out = peek.render(text, env)
    assert not _left_prefix(out, FAKE_A)
    assert not _left_prefix(out, FAKE_B)
    assert urllib.parse.quote(FAKE_B, safe="") not in out
    assert "[SERVER_FAKE_KEY=VITE_FAKE_KEY 가림]" in out          # 같은 값은 이름을 이어 붙임
    assert "[OTHER_FAKE 가림]" in out
    assert out.splitlines()[-1] == "[peek] 가림: OTHER_FAKE 3, SERVER_FAKE_KEY=VITE_FAKE_KEY 2"


def test_head_and_grep_apply_after_masking(env_file):
    env = peek.read_env(env_file)
    text = "".join(f"line {i} {FAKE_A}\n" for i in range(10))
    out = peek.render(text, env, head=2, grep=r"line [0-9]")
    lines = out.splitlines()
    assert len(lines) == 3 and not _left_prefix(out, FAKE_A)
    assert lines[-1] == "[peek] 가림: SERVER_FAKE_KEY=VITE_FAKE_KEY 10"


def test_short_and_empty_values_ignored(env_file):
    env = peek.read_env(env_file)
    assert "SHORT" not in env and "EMPTY" not in env
    assert peek.render("abc", env).splitlines()[-1] == "[peek] 가림: 없음"


def test_cli_file_and_stdin(env_file, tmp_path, capsys, monkeypatch):
    f = tmp_path / "bundle.js"
    f.write_text(f"x='{FAKE_A}'\n", encoding="utf-8")
    peek.main([str(f), "--env", str(env_file)])
    out = capsys.readouterr().out
    assert not _left_prefix(out, FAKE_A) and "가림" in out


@pytest.mark.parametrize("url", ["https://localhost:3000/x", "http://example.com/", "http://localhost:5173/",
                                 "http://192.168.0.2:8000/"])
def test_only_local_3000_8000(url):
    with pytest.raises(SystemExit):
        peek.fetch_local(url)
