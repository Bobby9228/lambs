import importlib.util
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"


def _load(name: str):
    # Ensure scripts/ is importable (so `from flags import ...` works)
    import sys

    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


memory_search = _load("memory_search")


def test_layer_weight_current_is_high():
    assert memory_search.layer_weight("CURRENT/stack.md") >= 4.0


def test_extract_snippet_missing_file_returns_empty(tmp_path, monkeypatch):
    # Point REPO to an empty temp dir
    monkeypatch.setattr(memory_search, "REPO", tmp_path)
    assert memory_search.extract_snippet("missing.md", 1) == ""


def test_grep_search_no_hits_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_search, "REPO", tmp_path)
    hits = memory_search.grep_search("does-not-exist", top=5)
    assert hits == []
