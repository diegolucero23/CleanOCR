"""
tests/test_redteam_scripts.py

Safety guardrails for the standalone RedTeam scripts in tests/redteam_artifacts/
(pytest does not collect that folder; these tests load the scripts by path).

Coverage:
  flood_queue.py
    - Aborts before sending any request when .env.redteam is missing
    - Aborts before sending any request when the mock kill-switch key is absent
    - Passes the interlock when the mock key is present
  stress_test.py
    - Has no unbounded top-level loop (safe to import)
    - Stops allocating once the configured memory cap is reached
"""

import ast
import importlib.util
from pathlib import Path

import pytest

ARTIFACTS_DIR = Path(__file__).resolve().parent / "redteam_artifacts"
MOCK_KEY = "MOCK_KEY_DO_NOT_CHARGE"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(f"redteam_{name}", ARTIFACTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# flood_queue.py
# ---------------------------------------------------------------------------
@pytest.fixture
def flood(monkeypatch):
    module = _load("flood_queue")
    sent = []
    monkeypatch.setattr(module.requests, "post", lambda *a, **kw: sent.append((a, kw)))
    module._sent = sent
    return module


def test_flood_aborts_when_env_file_missing(flood, tmp_path, monkeypatch):
    monkeypatch.setattr(flood, "ENV_FILE", tmp_path / ".env.redteam")
    with pytest.raises(SystemExit) as exc:
        flood.run_flood()
    assert exc.value.code != 0
    assert flood._sent == []


def test_flood_aborts_when_mock_key_absent(flood, tmp_path, monkeypatch):
    env_file = tmp_path / ".env.redteam"
    env_file.write_text("GOOGLE_API_KEY=AIzaRealLookingKey\n")
    monkeypatch.setattr(flood, "ENV_FILE", env_file)
    with pytest.raises(SystemExit) as exc:
        flood.run_flood()
    assert exc.value.code != 0
    assert flood._sent == []


def test_flood_interlock_passes_with_mock_key(flood, tmp_path, monkeypatch):
    env_file = tmp_path / ".env.redteam"
    env_file.write_text(f"GOOGLE_API_KEY={MOCK_KEY}\n")
    monkeypatch.setattr(flood, "ENV_FILE", env_file)
    flood.check_interlock()


@pytest.mark.parametrize("script", ["flood_queue", "fuzz_inputs"])
def test_interlock_env_file_resolves_from_repo_root(script, monkeypatch, tmp_path):
    """The interlock must find .env.redteam regardless of the caller's cwd
    (README documents running the scripts from the repository root)."""
    monkeypatch.chdir(tmp_path)
    module = _load(script)
    assert Path(module.ENV_FILE) == ARTIFACTS_DIR.parents[1] / ".env.redteam"


# ---------------------------------------------------------------------------
# stress_test.py
# ---------------------------------------------------------------------------
def _stress_test_runs_at_import() -> bool:
    """True if stress_test.py has loop/try statements at module level (allocates on import)."""
    tree = ast.parse((ARTIFACTS_DIR / "stress_test.py").read_text(encoding="utf-8"))
    return any(isinstance(node, (ast.While, ast.For, ast.Try)) for node in tree.body)


def test_stress_test_has_no_top_level_loop():
    assert not _stress_test_runs_at_import(), (
        "stress_test.py allocates at import time; wrap it in a function"
    )


def test_stress_test_stops_at_memory_cap(monkeypatch):
    if _stress_test_runs_at_import():
        pytest.fail("Refusing to import stress_test.py: it would allocate memory without a cap")
    module = _load("stress_test")
    monkeypatch.setattr(module.time, "sleep", lambda _s: None)
    assert module.run_stress(max_mb=30, chunk_mb=10) == 30
