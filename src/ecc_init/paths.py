from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppPaths:
    project_root: Path
    ecc_home: Path
    claude_home: Path

    @classmethod
    def build(cls, project_root: Path | None = None) -> "AppPaths":
        root = (project_root or Path.cwd()).expanduser().resolve()
        ecc_home = Path(os.environ.get("ECC_INIT_HOME", Path.home() / ".ecc-init")).expanduser().resolve()
        claude_home = Path(os.environ.get("CLAUDE_HOME", Path.home() / ".claude")).expanduser().resolve()
        return cls(project_root=root, ecc_home=ecc_home, claude_home=claude_home)

    @property
    def global_state(self) -> Path:
        return self.ecc_home / "state.json"

    @property
    def global_claude_md(self) -> Path:
        return self.claude_home / "CLAUDE.md"

    @property
    def global_skills(self) -> Path:
        return self.claude_home / "skills"

    @property
    def project_claude_md(self) -> Path:
        return self.project_root / "CLAUDE.md"

    @property
    def project_skills(self) -> Path:
        return self.project_root / ".claude" / "skills"

    @property
    def project_state(self) -> Path:
        return self.project_root / ".claude" / "ecc-init-state.json"

    @property
    def docs_dir(self) -> Path:
        return self.project_root / "docs"

    @property
    def backups_dir(self) -> Path:
        return self.ecc_home / "backups"

    @property
    def bases_dir(self) -> Path:
        return self.ecc_home / "bases"

    @property
    def cache_dir(self) -> Path:
        return self.ecc_home / "cache"
