# Manual Alpha Smoke Checklist

Run these commands in a temporary project directory to verify `ecc-init 0.2.0a1` behaviour. No real GSD Core or third-party installers are exercised.

## Prerequisites

- `ecc-init` installed via `pipx install .` or editable install
- Python 3.10+, Git available on PATH
- Temp directory for test projects

## Scenario 1: Empty Project

```powershell
$project = Join-Path $env:TEMP "ecc-smoke-empty"
New-Item -ItemType Directory -Force $project | Out-Null

# Plan
ecc-init plan $project --output (Join-Path $project "plan.json")

# Apply (bundled only, skip GSD checks for local test)
ecc-init apply (Join-Path $project "plan.json") --yes --skip-gsd-check --json

# Audit
ecc-init status $project --json
ecc-init doctor $project --mode audit --json

# Rollback by operation id (from apply output)
# ecc-init rollback $project --operation-id <id> --json
```

Expected:
- Only `project-baseline` and `quality-basic` Packs (no frontend/fastapi/rag)
- `.claude/ecc-sources.lock.json` exists with only `bundled` source
- `.claude/ecc-init-state.json` exists (schema v2)
- Operation receipt created under `ECC_INIT_HOME`
- Rollback removes generated files

## Scenario 2: FastAPI + LangGraph Project

```powershell
$project = Join-Path $env:TEMP "ecc-smoke-fastapi"
New-Item -ItemType Directory -Force $project | Out-Null
@'
[project]
name = "demo"
dependencies = ["fastapi", "langgraph"]
'@ | Out-File -FilePath (Join-Path $project "pyproject.toml") -Encoding utf8

ecc-init plan $project --output (Join-Path $project "plan.json")
ecc-init apply (Join-Path $project "plan.json") --yes --skip-gsd-check --json
ecc-init status $project --json
ecc-init doctor $project --mode audit --json
```

Expected:
- `python-fastapi` and `rag-python` Packs
- `.claude/skills/python-patterns/SKILL.md`
- `.claude/skills/fastapi-patterns/SKILL.md`
- `.claude/skills/langchain-patterns/SKILL.md`
- `.claude/skills/langgraph-patterns/SKILL.md`
- Status shows Packs with per-pack status

## Scenario 3: React + Vite Project

```powershell
$project = Join-Path $env:TEMP "ecc-smoke-react"
New-Item -ItemType Directory -Force $project | Out-Null
@'
{
  "dependencies": {
    "react": "^19.0.0",
    "vite": "^6.0.0"
  }
}
'@ | Out-File -FilePath (Join-Path $project "package.json") -Encoding utf8

ecc-init plan $project --output (Join-Path $project "plan.json")
ecc-init apply (Join-Path $project "plan.json") --yes --skip-gsd-check --json
ecc-init status $project --json
```

Expected:
- `frontend-essential` Pack
- Frontend lifecycle document
- React/TypeScript/UI skills
- Doctor reports frontend project detection

## Scenario 4: Existing GSD Config Project

```powershell
$project = Join-Path $env:TEMP "ecc-smoke-gsd-config"
New-Item -ItemType Directory -Force $project | Out-Null
$gsdConfig = Join-Path $project ".planning"
New-Item -ItemType Directory -Force $gsdConfig | Out-Null
@'
{"parallelization":{"enabled":false},"workflow":{"use_worktrees":false}}
'@ | Out-File -FilePath (Join-Path $gsdConfig "config.json") -Encoding utf8

@'
[project]
dependencies = ["fastapi"]
'@ | Out-File -FilePath (Join-Path $project "pyproject.toml") -Encoding utf8

ecc-init apply (Join-Path $project "plan.json") --yes --skip-gsd-check --json
```

Expected:
- GSD config `agent_skills` updated with installed Skill directories
- User-explicit `parallelization.enabled: false` preserved
- Rollback restores original config

## Scenario 5: Dry-Run Previews (No Writes)

```powershell
# All of these should produce JSON without writing files:
ecc-init init . --dry-run --json
ecc-init plan . --json
ecc-init apply plan.json --dry-run --json
ecc-init gsd install --dry-run --json
ecc-init gsd status --json
ecc-init update . --check --json
ecc-init doctor . --mode preflight --json
ecc-init migrate . --dry-run --json
```

Expected:
- All commands return valid JSON
- No files created under `.claude/`, `.planning/`, or `docs/`
- Exit codes 0 or non-zero depending on status (not crashes)
