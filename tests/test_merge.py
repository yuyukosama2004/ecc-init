from pathlib import Path

from ecc_init.backup import BackupSession
from ecc_init.merge import install_managed_section, install_whole_file


def test_managed_section_preserves_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "CLAUDE.md"
    target.write_text("# 我的规则\n\n不要覆盖。\n", encoding="utf-8")
    state: dict = {"managed_files": {}}
    backup = BackupSession(tmp_path / "backups", tmp_path)

    result = install_managed_section(
        target=target,
        section="<!-- start -->\n新规则\n<!-- end -->",
        source_id="test",
        start_marker="<!-- start -->",
        end_marker="<!-- end -->",
        state=state,
        bases_root=tmp_path / "bases",
        backup=backup,
    )

    content = target.read_text(encoding="utf-8")
    assert result.status == "updated"
    assert "不要覆盖" in content
    assert "新规则" in content


def test_whole_file_updates_when_local_unchanged(tmp_path: Path) -> None:
    target = tmp_path / "SKILL.md"
    state: dict = {"managed_files": {}}
    backup1 = BackupSession(tmp_path / "backups", tmp_path)
    install_whole_file(
        target=target,
        incoming="v1\n",
        source_id="skill",
        state=state,
        bases_root=tmp_path / "bases",
        backup=backup1,
    )

    backup2 = BackupSession(tmp_path / "backups", tmp_path)
    result = install_whole_file(
        target=target,
        incoming="v2\n",
        source_id="skill",
        state=state,
        bases_root=tmp_path / "bases",
        backup=backup2,
    )

    assert result.status == "updated"
    assert target.read_text(encoding="utf-8") == "v2\n"


def test_three_way_merge_preserves_non_overlapping_local_edit(tmp_path: Path) -> None:
    target = tmp_path / "SKILL.md"
    state: dict = {"managed_files": {}}
    first = BackupSession(tmp_path / "backups", tmp_path)
    install_whole_file(
        target=target,
        incoming="alpha\nbeta\nmiddle\ndelta\ngamma\n",
        source_id="skill",
        state=state,
        bases_root=tmp_path / "bases",
        backup=first,
    )
    target.write_text("alpha\nbeta-local\nmiddle\ndelta\ngamma\n", encoding="utf-8")

    second = BackupSession(tmp_path / "backups", tmp_path)
    result = install_whole_file(
        target=target,
        incoming="alpha\nbeta\nmiddle\ndelta\ngamma-upstream\n",
        source_id="skill",
        state=state,
        bases_root=tmp_path / "bases",
        backup=second,
    )

    assert result.status == "updated"
    content = target.read_text(encoding="utf-8")
    assert "beta-local" in content
    assert "gamma-upstream" in content


def test_conflict_keeps_local_and_writes_comparison(tmp_path: Path) -> None:
    target = tmp_path / "SKILL.md"
    state: dict = {"managed_files": {}}
    first = BackupSession(tmp_path / "backups", tmp_path)
    install_whole_file(
        target=target,
        incoming="value=base\n",
        source_id="skill",
        state=state,
        bases_root=tmp_path / "bases",
        backup=first,
    )
    target.write_text("value=local\n", encoding="utf-8")

    second = BackupSession(tmp_path / "backups", tmp_path)
    result = install_whole_file(
        target=target,
        incoming="value=upstream\n",
        source_id="skill",
        state=state,
        bases_root=tmp_path / "bases",
        backup=second,
    )

    assert result.status == "conflict"
    assert target.read_text(encoding="utf-8") == "value=local\n"
    assert target.with_name("SKILL.md.ecc-upstream").exists()
    assert target.with_name("SKILL.md.ecc-diff").exists()
