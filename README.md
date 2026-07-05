# ecc-init

`ecc-init` 是一个轻量 Claude Code 配置初始化器。它不安装完整 ECC，而是：

- 创建或合并全局 `~/.claude/CLAUDE.md`；
- 全局安装 6 个通用 Skill；
- 自动识别当前项目技术栈；
- 只在项目内安装匹配的技术栈 Skill；
- 初始化项目导读和开发复盘目录；
- 自动尝试同步 ECC 的稳定版技术栈 Skill；
- 网络失败时使用本地缓存或内置模板；
- 更新前备份，使用三方合并保留本地修改；
- 冲突时保留本地版本，并生成 `.ecc-upstream` 和 `.ecc-diff`。

当前版本为 **0.2.0a0 Alpha**，用于验证 GSD-first 架构、迁移路径和发布流程。

## 路线状态

`0.1.x` 是 legacy 初始化器：它保留当前 Python CLI、检测、合并、备份和回滚行为。
`0.2.0 Alpha` 默认切换为以 GSD Core 为唯一主工作流内核的架构；不会 Fork、vendor 或直接修改 GSD。

## 0.2.0 Alpha Behavior

`ecc-init init .` now defaults to the GSD declarative plan. It previews the selected workflow, Packs, file operations, and pinned external commands without installing legacy workflow skills.

GSD Core is a device/runtime-level workflow kernel. Install it once for the runtime you use, for example:

```powershell
ecc-init gsd status --json
ecc-init gsd install --yes
ecc-init gsd verify
```

For Claude global installs, `ecc-init` plans the pinned official installer as:

```powershell
npx -y @opengsd/gsd-core@1.6.1 --claude --global
```

Project Packs are separate. They are selected per project from the declarative registry and applied through an InstallPlan:

```powershell
ecc-init plan . --output ecc-plan.json
ecc-init apply ecc-plan.json --dry-run --json
ecc-init apply ecc-plan.json --yes --json
```

`apply` now produces a structured `ApplyReport` with plan validation, project-root validation, planned files, GSD status, and optional GSD config sync reporting. With `--yes`, the transactional apply path installs bundled project-scope Pack files and explicitly configured pinned GitHub archive project files, writes `.claude/ecc-sources.lock.json`, updates state v2 managed-file ownership, merges existing `.planning/config.json` GSD config unless `--no-sync-gsd` is supplied, writes an operation receipt, and can be rolled back by operation id.

Legacy 0.1.x writes are still available for migration compatibility:

```powershell
ecc-init init . --legacy --offline
```

GSD Core is external. `ecc-init` plans the pinned official package `@opengsd/gsd-core@1.6.1`; it does not fork, vendor, copy selected GSD internals, or modify GSD Core.

## 支持的技术栈

首版支持自动识别：

- Python
- FastAPI
- LangChain
- LangGraph
- TypeScript
- React
- Java
- Spring Boot

## Frontend Pack

React projects are selected for the declarative `frontend-essential` Pack. The Pack previews bundled React/TypeScript, UI UX Pro Max, Vercel, and Playwright-quality skills, writes a frontend lifecycle document in the install plan, and contributes GSD UI agent skill mappings through `ecc-init sync-gsd`.

`ecc-init doctor` reports frontend project, Playwright, Vercel, and GSD Browser detection status. These checks are informational and do not install third-party tools.

## Stack Packs

The declarative Pack registry includes Python/FastAPI, RAG Python, and Java/Spring stack Packs. Components are filtered by detected stack evidence, so a plain Python project receives Python guidance without FastAPI, a LangChain-only project receives LangChain guidance without LangGraph, and a Java-only project receives Java guidance without Spring Boot.

Project stack skills include frontmatter metadata with `source_id` and `content_version`. ECC-derived source policy is pinned to a fixed `affaan-m/ECC` commit in the registry, while bundled fallback resources keep ordinary offline plan generation deterministic. Explicit pinned GitHub archive components can be projected by apply when their fixed archive is available or fetching is allowed.

## 全局 Skill

安装到 `~/.claude/skills/`：

- `task-planning`
- `verification-loop`
- `code-review`
- `security-review`
- `code-tour`
- `dev-retrospective`

These global workflow skills are installed only by the explicit legacy path:

```powershell
ecc-init init . --legacy
```

## 安装

### 使用源码目录安装

Windows PowerShell：

```powershell
cd path\to\ecc-init
pipx install .
```

若已安装，需要覆盖当前版本：

```powershell
pipx install . --force
```

也可以开发模式测试：

```powershell
python -m pip install -e .
```

## 使用

在任意 Demo 项目目录运行：

```powershell
ecc-init
```

也可以指定项目目录：

```powershell
ecc-init D:\Projects\my-demo
```

其他命令：

```powershell
ecc-init plan
ecc-init apply ecc-plan.json --dry-run --json
ecc-init gsd status
ecc-init gsd install --dry-run --json
ecc-init gsd install --yes
ecc-init gsd update --dry-run --json
ecc-init gsd verify
ecc-init packs list
ecc-init packs show frontend-essential
ecc-init sources list
ecc-init sources verify
ecc-init workflow status
ecc-init sync-gsd --dry-run
ecc-init migrate --dry-run
ecc-init migrate
ecc-init status
ecc-init status --json
ecc-init update --check --json
ecc-init remove --pack frontend-essential
ecc-init remove --pack frontend-essential --yes
ecc-init doctor --json
ecc-init rollback
ecc-init rollback --operation-id <operation-id>
```

### Lifecycle commands

PowerShell preview commands are write-free:

```powershell
ecc-init init . --dry-run --json
ecc-init gsd install --dry-run --json
ecc-init apply ecc-plan.json --dry-run --json
ecc-init update . --check --json
ecc-init update . --packs --dry-run --json
ecc-init remove . --pack frontend-essential --json
ecc-init doctor . --json
```

Write operations require explicit non-interactive confirmation:

```powershell
ecc-init gsd install --yes
ecc-init apply ecc-plan.json --yes --json
ecc-init update . --packs --yes --json
ecc-init remove . --pack frontend-essential --yes --json
```

`init . --yes` enters the project-level apply path and does not install GSD Core by default. Use `init . --yes --install-gsd` only when you intentionally want the device/runtime-level GSD install step included. `apply --yes` currently writes bundled and explicit pinned GitHub archive project-scope Pack files transactionally, and only syncs GSD config when `.planning/config.json` already exists. Missing GSD config is not created. Non-project and unsupported component installs are guarded. `remove` only edits ecc-init managed GSD config bindings in this phase. It does not delete user-modified Skill files or uninstall GSD Core.

### Legacy v1 migration

`ecc-init migrate --dry-run` previews removal of the legacy v1 workflow markers and deprecated global workflow skills without writing files.

`ecc-init migrate` applies the v1-to-v2 state migration, writes `docs/ecc-init-migration-report.md`, records an operation receipt, and can be reverted with:

```powershell
ecc-init rollback --operation-id <operation-id>
```

User-modified legacy skills are preserved and reported for manual review.

离线运行：

```powershell
ecc-init init . --legacy --offline
```

完全禁用 ECC 上游同步，只使用包内模板：

```powershell
ecc-init init . --legacy --no-sync
```

## 生成结构

The structure below applies to `ecc-init init --legacy`. The 0.2.0a0 default `init` path previews the GSD declarative plan instead of writing these legacy files.

全局：

```text
~/.claude/
├── CLAUDE.md
└── skills/
    ├── task-planning/
    ├── verification-loop/
    ├── code-review/
    ├── security-review/
    ├── code-tour/
    └── dev-retrospective/
```

项目：

```text
项目/
├── CLAUDE.md
├── .claude/
│   ├── ecc-init-state.json
│   └── skills/
│       └── 根据技术栈自动安装
└── docs/
    ├── DEVELOPMENT_LOG.md
    ├── PROJECT_OVERVIEW.md
    └── dev-notes/
```

## 合并策略

### CLAUDE.md

`ecc-init` 只管理带标记的区域：

```markdown
<!-- ecc-init:start global -->
...
<!-- ecc-init:end global -->
```

或：

```markdown
<!-- ecc-init:start project -->
...
<!-- ecc-init:end project -->
```

首次遇到已有 `CLAUDE.md` 时会保留原文，并追加管理区域。

### Skill

`ecc-init` 保存上次安装的模板作为三方合并基线：

- 本地未修改：直接更新；
- 本地和新版修改不冲突：自动合并；
- 自动合并冲突：保留本地版本，另存上游新版和 diff。

三方合并依赖 Git。没有 Git 时不会覆盖有冲突风险的本地文件。

## 备份和回滚

所有变更前会在以下目录创建备份：

```text
~/.ecc-init/backups/
```

恢复最近一次操作：

```powershell
ecc-init rollback
```

恢复指定备份：

```powershell
ecc-init rollback --backup 20260628_120000_000000
```

## 环境变量

测试或自定义目录时可使用：

```text
ECC_INIT_HOME   ecc-init 状态、缓存和备份目录
CLAUDE_HOME     Claude Code 配置目录
```

## 自动同步说明

当前版本会从 `affaan-m/ECC` 的最新 GitHub Release 获取可对应的技术栈 Skill：

- Python
- FastAPI
- React
- Java
- Spring Boot

LangChain、LangGraph、TypeScript，以及 6 个全局 Skill 使用本包内的定制模板。定制模板的新版通过升级 `ecc-init` 包获得。

若 GitHub Release 查询或下载失败，会继续使用上次缓存；没有缓存时使用包内模板，不中断初始化。

## 当前限制

- 自动识别以项目根目录的配置文件和有限数量源码为依据，复杂 monorepo 可能需要后续扩展。
- “第一次进入项目自动 code-tour”由 `CLAUDE.md` 规则在 Claude 接到任务时触发，不是后台守护进程。
- 开发复盘由 Claude 在中大型任务三个阶段更新，初始化器只负责目录、模板和行为规则。
- 目前没有自动删除已经不再匹配的旧项目 Skill，避免误删用户修改；可手动清理。
- 上游 Skill 结构变化时可能产生对比文件，需要人工决定是否吸收新版。

## 来源与许可

本项目借鉴并选择性同步 [affaan-m/ECC](https://github.com/affaan-m/ECC) 中的 Skill 设计。ECC 来源文件保留其原项目许可与归属；本项目自定义代码和模板使用 MIT License。
