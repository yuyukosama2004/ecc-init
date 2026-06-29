from ecc_init.cli import _normalize_argv


def test_default_command_accepts_offline_flag() -> None:
    assert _normalize_argv(["--offline"]) == ["init", "--offline"]


def test_explicit_status_is_preserved() -> None:
    assert _normalize_argv(["status", "."]) == ["status", "."]
