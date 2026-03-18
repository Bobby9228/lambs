from pathlib import Path


def test_flags_invalid_values_warn_and_default(tmp_path, capsys, monkeypatch):
    flags_file = tmp_path / ".lambs_flags"
    flags_file.write_text(
        "LAMBS_SEARCH_ENABLED=true\nLAMBS_SEMANTIC_ENABLED=2\nLAMBS_PATTERN_ENABLED=0\n"
    )

    monkeypatch.setenv("LAMBS_FLAGS_FILE", str(flags_file))

    # Import after env var set
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from flags import load_flags

    f = load_flags()
    assert f.search is True  # invalid -> default 1
    assert f.semantic is False  # invalid -> default 0
    assert f.pattern is False  # valid 0

    captured = capsys.readouterr()
    assert "WARN" in captured.err
