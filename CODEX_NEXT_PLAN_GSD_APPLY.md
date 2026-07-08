# ecc-init 下一阶段完整开发计划书：GSD 安装语义与完整 Apply 闭环

> 建议文件名：`CODEX_NEXT_PLAN_GSD_APPLY.md`  
> 执行工具：Codex  
> 目标仓库：`https://github.com/yuyukosama2004/ecc-init`  
> 当前基线：`ecc-init 0.2.0a0 Alpha`  
> 目标版本：`0.2.0a1 Alpha` 或 `0.2.0b0 Beta-prep`  
> 核心目标：把当前“GSD-first 预览型框架管理器”推进为“能安全安装 GSD、真正 apply Pack、写 Source Lock/Receipt、可回滚、可 E2E 验证”的可用闭环。  
> 非目标：不 Fork GSD，不 vendor GSD，不复制 GSD 内部 commands/agents/hooks，不重新实现 GSD/Superpowers/ECC 的主工作流。

---

## 0. 当前判断

当前仓库已经完成 `0.2.0a0` Alpha 骨架：

- 默认 `init` 已经从 legacy 写入改成 GSD-first declarative plan preview；
- 已有 Pack Registry；
- 已有 Source Provider 基础；
- 已有 GSD Config Bridge；
- 已有 Agent Policy Profile；
- 已有 Legacy v1 Migration；
- 已有 ReceiptStore；
- 已有 SourceLockStore；
- 已有 `plan / packs / sources / workflow / sync-gsd / migrate / update / remove / apply` 等 CLI；
- 已有较多单元测试、迁移测试、workflow fake-runner 测试和 release smoke。

但是当前还不是完整可用框架，因为仍缺少关键闭环：

```text
InstallPlan
  → apply
  → 安装/确认 GSD Core
  → 安装项目能力包 Skill
  → 写入 Source Lock
  → 写入 Operation Receipt
  → sync-gsd
  → doctor 验证
  → rollback
```

当前最重要的缺口：

1. `apply` 仍是 validate-only；
2. `GsdWorkflowAdapter` 的 install/update 语义需要和 GSD 官方 installer 对齐；
3. Source Provider 没有真正接入 component projection/install；
4. Pack 安装还没有变成事务型文件写入；
5. `init --yes` 现在语义容易混淆，不能继续把 update 当 install；
6. GSD Core 应该完整安装一次，Pack 才是按项目选择性安装；
7. 真实 E2E 要围绕 empty / FastAPI+LangGraph / React+Vite 三类项目跑完整生命周期。

---

## 1. 最高优先级架构原则

### 1.1 GSD Core 的安装原则

GSD Core 是完整工作流内核，必须完整安装。

严禁：

```text
复制 GSD commands/
复制 GSD agents/
复制 GSD hooks/
只挑几个 GSD 文件安装
修改 GSD 内部文件
vendor GSD 源码进 ecc-init 仓库
```

允许：

```text
调用 GSD 官方 installer
记录 pinned version
记录 install command
检查 runtime/scope
检查安装结果
通过 .planning/config.json 做项目级配置
通过 agent_skills 接入 ecc-init 的项目 Skill
```

### 1.2 Pack 的安装原则

选择性安装只发生在 ecc-init Pack 层。

```text
GSD Core：完整安装，一台设备或一个 runtime 通常安装一次
ecc-init Packs：按项目技术栈选择性安装，每个项目初始化一次
GSD config sync：按项目合并配置，需要时运行
日常开发：直接使用 GSD 命令
```

### 1.3 三层安装模型

#### 设备级 / Runtime 级

```bash
ecc-init gsd status
ecc-init gsd install --yes
ecc-init gsd update --yes
```

作用：

- 检查 Node/npm/npx；
- 安装完整 GSD Core；
- 验证 GSD 是否可被当前 Claude Code runtime 使用；
- 不安装项目 Pack；
- 不修改项目业务文件。

#### 项目级

```bash
ecc-init plan . --output plan.json
ecc-init apply plan.json --yes
```

作用：

- 检测项目技术栈；
- 解析 Profile 和 Pack；
- 安装项目级 Skill；
- 写 docs；
- 写 Source Lock；
- 写 Receipt；
- 不重复安装 GSD Core，除非用户显式要求。

#### 项目配置同步

```bash
ecc-init sync-gsd .
```

作用：

- 读取 `.planning/config.json`；
- 合并 `parallelization` / `workflow` 默认值；
- 合并 `agent_skills`；
- 保留用户显式配置；
- 不创建 GSD 项目；
- 不安装 GSD。

---

## 2. Codex 执行契约

Codex 开始前必须读取：

```text
AGENTS.md
DEVELOPMENT_PLAN_CODEX.md
CODEX_NEXT_PLAN_GSD_APPLY.md
README.md
ARCHITECTURE.md
MIGRATION.md
SOURCE_POLICY.md
SECURITY.md
docs/internal/IMPLEMENTATION_STATUS.md
```

### 2.1 第一批必须先做

1. 确认当前仓库：
   ```bash
   git status --short
   git branch --show-current
   git log -5 --oneline
   ```

2. 跑当前测试：
   ```bash
   python -m pytest
   python -m compileall -q src scripts
   git diff --check
   ```

3. 如果本地无 pytest：
   - 建临时 venv；
   - 安装 pinned pytest；
   - 不修改项目 dependencies。

4. 更新：
   ```text
   docs/internal/IMPLEMENTATION_STATUS.md
   ```

5. 第一批不使用并行写 Agent。

### 2.2 子 Agent 限制

当前阶段涉及安装、文件写入、回滚和供应链，属于高风险任务。

默认限制：

```text
主 Agent：负责设计、实现、整合、最终验证
只读 Explorer：最多 1
只读 Reviewer：最多 1
并行 Write Worker：0
嵌套深度：1
同一子任务重试：最多 1 次
Reviewer 复审：最多 2 轮
```

如果确实需要并行写：

- 必须先写 File Ownership Table；
- 文件集合完全不重叠；
- 不得共同修改 core models / app.py / cli.py / transaction / source provider；
- 必须使用 worktree 或明确分支；
- 需用户明确批准。

---

## 3. 目标用户体验

### 3.1 第一次在设备上安装 GSD

```bash
ecc-init gsd status
ecc-init gsd install --yes
ecc-init gsd status
```

期望：

```text
Node.js: PASS
npm/npx: PASS
GSD Core package: @opengsd/gsd-core@1.6.1
Runtime: claude
Scope: global
Install command: npx -y @opengsd/gsd-core@1.6.1 --claude --global
Status: installed or installed_unverified
```

如果无法稳定识别 GSD 安装文件，不要假装成功 verified。应该输出 `installed_unverified`，并告诉用户运行 GSD 命令确认。

### 3.2 初始化项目

```bash
ecc-init plan . --output ecc-plan.json
ecc-init apply ecc-plan.json --yes
```

期望：

```text
Project detected: python, fastapi, langgraph
Workflow: gsd
Packs:
- project-baseline
- quality-basic
- python-fastapi
- rag-python

Files written:
- .claude/skills/python-patterns/SKILL.md
- .claude/skills/fastapi-patterns/SKILL.md
- .claude/skills/langchain-patterns/SKILL.md
- .claude/skills/langgraph-patterns/SKILL.md
- docs/PROJECT_OVERVIEW.md
- docs/DEVELOPMENT_LOG.md

Source lock:
- bundled
- ecc-upstream-pinned if used

Receipt:
- ~/.ecc-init/operations/<operation-id>/receipt.json
```

### 3.3 如果 GSD 项目已初始化

```bash
ecc-init sync-gsd . --dry-run
ecc-init sync-gsd .
```

期望：

```text
.planning/config.json existed
parallelization defaults merged without overwriting user values
agent_skills added only for existing SKILL.md directories
operation receipt written if changed
```

### 3.4 如果 GSD 未初始化

```bash
ecc-init sync-gsd .
```

期望：

```text
GSD config not initialized
No .planning/config.json was created
Suggested next step: run /gsd-new-project or equivalent GSD init command
```

### 3.5 日常开发

用户使用 GSD：

```text
/gsd-new-project
/gsd-discuss-phase
/gsd-plan-phase
/gsd-execute-phase
/gsd-verify-work
/gsd-ship
```

`ecc-init` 不参与每一次开发任务执行。

---

## 4. 命令设计

### 4.1 新增 `gsd` 命令组

新增：

```bash
ecc-init gsd status
ecc-init gsd install
ecc-init gsd update
ecc-init gsd verify
```

参数：

```text
--runtime claude|codex|cursor|auto
--scope global|project
--version 1.6.1
--dry-run
--yes
--json
```

默认：

```text
runtime = claude
scope = global
version = registry pinned version
dry-run = true unless --yes
```

### 4.2 `init` 语义

当前 `init` 默认 preview 可以保留，但要去除歧义。

建议：

```bash
ecc-init init .
```

等价于：

```bash
ecc-init plan .
```

只预览，不写。

```bash
ecc-init init . --yes
```

建议行为：

```text
生成 plan
检查 GSD status
如果 GSD 未安装：提示用户先 ecc-init gsd install --yes，除非 --install-gsd
apply plan
如果 .planning/config.json 存在：sync-gsd
```

可选参数：

```text
--install-gsd
```

如果用户传了：

```bash
ecc-init init . --yes --install-gsd
```

则允许：

```text
安装 GSD
apply Pack
sync-gsd
```

但仍要清楚输出设备级与项目级操作的边界。

### 4.3 `apply` 语义

当前 `apply` 是 validate-only。目标改成：

```bash
ecc-init apply ecc-plan.json --yes
```

默认不写：

```bash
ecc-init apply ecc-plan.json
```

应输出：

```text
No --yes supplied; apply is dry-run preview.
```

参数：

```text
--dry-run
--yes
--json
--skip-gsd-check
--sync-gsd
--no-sync-gsd
--offline
```

默认：

```text
dry-run = true unless --yes
sync-gsd = true if .planning/config.json exists
offline = false
```

---

## 5. GSD Adapter 详细计划

### 5.1 当前问题

当前 `GsdWorkflowAdapter` 大致有：

```text
install: npx -y @opengsd/gsd-core@1.6.1
update: npm install -g @opengsd/gsd-core@1.6.1
```

这不够精确。

问题：

1. `install` 缺少 runtime/scope 参数；
2. `update` 语义不像 GSD runtime install；
3. `init --yes` 走 update surface 容易误导；
4. 缺少“已安装检测”；
5. 缺少“GSD runtime 文件是否可用”的验证；
6. 缺少设备级与项目级的清晰边界。

### 5.2 目标接口

文件：

```text
src/ecc_init/workflows/gsd.py
```

重构为：

```python
@dataclass(frozen=True)
class GsdInstallOptions:
    runtime: str = "claude"
    scope: str = "global"
    version: str = GSD_PINNED_VERSION
    yes: bool = False
    dry_run: bool = True

class GsdWorkflowAdapter:
    def environment_checks(self) -> list[EnvironmentCheck]: ...
    def install_command(self, options: GsdInstallOptions) -> PlannedCommand: ...
    def install(self, paths: AppPaths, options: GsdInstallOptions) -> WorkflowResult: ...
    def status(self, paths: AppPaths, runtime: str, scope: str) -> WorkflowResult: ...
    def verify(self, paths: AppPaths, runtime: str, scope: str) -> WorkflowResult: ...
    def update(self, paths: AppPaths, options: GsdInstallOptions) -> WorkflowResult: ...
    def remove_strategy(self, paths: AppPaths, runtime: str, scope: str) -> WorkflowResult: ...
```

### 5.3 GSD install command

对于 Claude global：

```bash
npx -y @opengsd/gsd-core@1.6.1 --claude --global
```

对于 Claude project/local：

```bash
npx -y @opengsd/gsd-core@1.6.1 --claude --local
```

如果官方 installer 当前参数不同，Codex 必须：

1. 查阅当前 GSD docs / package help；
2. 更新测试；
3. 在 `SOURCE_POLICY.md` 记录；
4. 不猜测 silent 参数。

### 5.4 环境检查

必须检查：

```text
node present
npm present
npx present
node version >= GSD official requirement
CLAUDE_HOME writable if global
project root writable if local
```

当前代码是 Node 18+。如果 registry / docs 要求不同，必须统一。

### 5.5 安装结果验证

Claude global 模式下至少检查：

```text
CLAUDE_HOME exists
expected GSD command/agent artifacts exist
or installer reported success and doctor can find GSD marker
```

如果无法稳定识别 GSD 安装文件：

- 只报告 command success；
- status 输出 `installed_unverified`；
- 明确说明需要用户运行 GSD command 验证；
- 不假装完全确认。

### 5.6 测试

新增/修改：

```text
tests/test_gsd_install_cli.py
tests/test_workflows.py
```

测试项：

- install command includes `--claude --global`;
- local command includes local/project scope;
- no shell=True;
- Windows uses `.cmd`;
- missing node blocks;
- old node blocks;
- dry-run does not execute npx;
- `ecc-init gsd install --dry-run --json`;
- `ecc-init gsd install --yes --json` with FakeRunner;
- `init --yes` does not call update as install;
- status with no GSD gives actionable message.

---

## 6. InstallPlan Apply 详细计划

### 6.1 当前状态

`InstallPlan` 已存在，`apply` 当前 validate-only。

目标：

```text
apply 必须变成完整事务型项目安装入口
```

### 6.2 Apply Pipeline

```text
load plan
→ validate plan
→ validate current project root
→ load registry
→ load source locks
→ preflight
→ create transaction
→ resolve sources
→ stage components
→ write component files
→ write source lock
→ write project state v2
→ maybe sync-gsd
→ write receipt
→ verify
→ commit transaction
```

### 6.3 Apply 不负责什么

第一版 `apply` 不负责：

- 安装完整 GSD Core，除非 `--install-gsd`；
- 运行 `/gsd-new-project`；
- 创建 `.planning/config.json`；
- 下载 optional Vercel/Anthropic/UI UX CLI 内容；
- 更新第三方 source 到新版本；
- 删除旧 legacy files；
- 执行用户项目测试。

### 6.4 Plan 校验

校验项：

```text
schema_version == 2
project_root == current or explicitly allowed
workflow exists in registry
packs exist in registry
file operations match resolved components
no path traversal
no absolute target outside allowed root
source ids exist
component ids exist
operation ids unique
required components resolvable
```

如果 plan 项目路径和当前路径不一致：

- 默认拒绝；
- 允许 `--allow-project-root-mismatch` 但不建议第一版加。

### 6.5 事务模型

文件：

```text
src/ecc_init/core/transaction.py
src/ecc_init/apply.py
```

事务目录：

```text
~/.ecc-init/operations/<operation-id>/
├── plan.json
├── pre-state.json
├── file-journal.json
├── source-lock-before.json
├── receipt.json
├── rollback-report.json
└── logs/
```

写入原则：

- 写文件前 `backup.record_before_change(path)`；
- 写文件后记录 hash；
- 失败自动 rollback；
- 如果 rollback 遇到用户并发修改，跳过并报告；
- `Receipt.result` 必须区分：
  - success
  - failed
  - rolled_back
  - rollback_partial

### 6.6 Apply Report

新增：

```python
@dataclass
class ApplyReport:
    project_root: Path
    dry_run: bool
    applied: bool
    operation_id: str | None
    backup_id: str | None
    plan: InstallPlan
    files_planned: list[...]
    files_written: list[...]
    sources_locked: list[...]
    config_report: ConfigSyncReport | None
    warnings: list[str]
    errors: list[str]
```

JSON 输出必须稳定。

---

## 7. Component Installer 详细计划

### 7.1 目标

把 registry 中的 component 真正安装到目标路径。

当前 registry component 示例：

```json
{
  "component_id": "skill-python-patterns",
  "source_id": "bundled",
  "install_name": "python-patterns",
  "target_scope": "project",
  "target_subdir": ".claude/skills/python-patterns/SKILL.md",
  "projection_include": ["project_skills/python-patterns/SKILL.md"],
  "stack_conditions": ["python"]
}
```

### 7.2 Bundled Component 安装

第一版只要求完整支持 `bundled` source。

流程：

```text
resolve bundled source root
→ 找 projection_include
→ 如果只有一个文件且 target_subdir 是文件：写入 target file
→ 如果 projection 是目录：复制目录
→ preserve user local edits
→ record owner/source/hash
```

### 7.3 GitHub Archive Component 安装

第二批再做。

流程：

```text
resolve fixed commit archive
→ safe_extract_zip
→ find source path
→ project_directory
→ copy to staging
→ install into target
→ write SourceLock
```

### 7.4 Optional Source Policy

当前这些 source 不应被真实下载：

```text
vercel-skills optional_policy
anthropic-frontend-policy optional_policy
```

Apply 行为：

- required=false：跳过并 warning；
- required=true 且 source kind unsupported：失败；
- declaration-only source 不写文件。

### 7.5 文件合并策略

对 `SKILL.md`：

- 如果目标不存在：create；
- 如果目标存在且未被管理：preserve by default，写 `.ecc-upstream` 或报 conflict；
- 如果目标存在且 managed hash 未变：replace/update；
- 如果目标存在且 user modified：preserve，写 upstream/diff；
- 如果 `--force` 未设计，第一版不要覆盖。

复用现有：

```text
install_whole_file
install_managed_section
```

不要重新造低级 merge，除非现有函数无法满足。

### 7.6 Ownership

安装后 state v2 记录：

```json
{
  "managed_files": {
    "/abs/path/.claude/skills/python-patterns/SKILL.md": {
      "source_id": "bundled",
      "component_id": "skill-python-patterns",
      "owners": ["pack:python-fastapi"],
      "sha256": "...",
      "base_hash": "...",
      "content_version": "..."
    }
  }
}
```

如果一个文件被多个 Pack 共用：

```json
"owners": ["pack:quality-basic", "pack:security-deep"]
```

---

## 8. Source Lock 详细计划

### 8.1 目标路径

项目级：

```text
.claude/ecc-sources.lock.json
```

全局源如果写全局 Skill，可记录到：

```text
~/.ecc-init/source-lock.json
```

第一版优先项目级。

### 8.2 内容

```json
{
  "schema_version": 1,
  "sources": {
    "bundled": {
      "source_id": "bundled",
      "repository": "https://github.com/yuyukosama2004/ecc-init",
      "resolved_ref": "0.2.0a1",
      "integrity": "sha256:...",
      "source_path": "src/ecc_init/resources",
      "license_id": "MIT",
      "license_path": null
    }
  }
}
```

### 8.3 写入时机

每次 `apply --yes` 成功安装组件后写。

如果只是 plan 或 dry-run，不写。

### 8.4 校验

`doctor` 增加：

```text
source lock exists
source lock schema valid
all managed source ids known
hash available
unsupported source kind warnings
```

---

## 9. Receipt 详细计划

### 9.1 Receipt 必须覆盖 apply

现在 ReceiptStore 已有。下一步 apply 必须写 receipt。

内容：

```json
{
  "schema_version": 2,
  "operation_id": "...",
  "created_at": "...",
  "project_root": "...",
  "operation": "apply",
  "workflow": {
    "id": "gsd",
    "status": "required|installed|not-installed|skipped"
  },
  "packs": [
    {"pack_id": "python-fastapi", "version": 1}
  ],
  "sources": [
    {"source_id": "bundled", "resolved_ref": "0.2.0a1"}
  ],
  "files": [
    {
      "path": ".claude/skills/python-patterns/SKILL.md",
      "owner": "pack:python-fastapi",
      "sha256": "...",
      "previous_sha256": null,
      "status": "created"
    }
  ],
  "config_changes": [
    {
      "path": ".planning/config.json",
      "action": "sync-gsd",
      "status": "changed|skipped"
    }
  ],
  "backup_id": "...",
  "result": "success"
}
```

### 9.2 Rollback

`rollback --operation-id` 应能回滚 apply 写入的文件。

测试：

- create files then rollback removes them；
- update files then rollback restores previous；
- user concurrent edit after apply then rollback preserves user edit and reports partial；
- source lock restored；
- receipt remains for audit。

---

## 10. State v2 详细计划

### 10.1 当前问题

legacy init 仍写 v1 state； migration 写 v2 state。apply 需要直接写 v2 state。

### 10.2 Apply 后 state

目标路径：

```text
.claude/ecc-init-state.json
```

结构：

```json
{
  "schema_version": 2,
  "tool_version": "0.2.0a1",
  "project_root": "...",
  "detected_stacks": ["python", "fastapi"],
  "detection_evidence": {},
  "workflow": {
    "id": "gsd",
    "scope": "global",
    "required_version": "1.6.1",
    "installed": true,
    "verified": false
  },
  "profiles": ["default"],
  "agent_policy": {
    "profile": "default",
    "max_concurrent_agents": 3,
    "plan_level_parallel": true,
    "task_level_parallel": false,
    "advisory_phase_budget": 8
  },
  "packs": {
    "project-baseline": {"version": 1},
    "python-fastapi": {"version": 1}
  },
  "managed_files": {},
  "source_locks": {},
  "pending_gsd_config": {},
  "last_operation_id": "...",
  "last_initialized_at": "..."
}
```

### 10.3 兼容

- 如果已有 v1：提示 migrate，不自动破坏；
- 如果已有 v2：merge；
- 如果用户修改 managed files：preserve / conflict。

---

## 11. Doctor 扩展

### 11.1 当前 doctor

已有：

- Python；
- Git；
- ecc-init 数据目录；
- Claude 配置目录；
- 当前项目目录；
- 内置清单；
- GSD config bridge；
- GSD hard/advisory policy；
- frontend checks。

### 11.2 新增检查

增加：

```text
GSD package/runtime status
GSD install scope
GSD install command preview
Source lock status
Receipt status
Plan/apply consistency
Managed files dirty
Unsupported source kinds
Apply readiness
```

### 11.3 输出示例

```text
[PASS] Python: 3.12.4
[PASS] Git three-way merge: C:\Program Files\Git\cmd\git.exe
[PASS] Node.js: v22.12.0
[PASS] npx: C:\Program Files\nodejs\npx.cmd
[WARN] GSD Core runtime: not verified
[PASS] Project source lock: .claude/ecc-sources.lock.json
[PASS] Managed files: clean
[WARN] GSD config: not initialized; run /gsd-new-project before sync-gsd
```

---

## 12. Update/Remove 后续策略

### 12.1 update

当前 `update --sources` 只是 verify declarations。

下一步不要急着实现真正 remote update，先保证：

```text
update --check
  → 比较 registry 当前 version 与 lock
  → 报告可更新/不可判断
  → 不下载
```

后续再加：

```text
update --sources --yes
```

### 12.2 remove

当前只删 GSD config binding。

下一阶段可增加：

```text
remove --pack X --files --yes
```

但默认仍然只删 config binding。

完整删除文件必须满足：

1. 文件由 ecc-init 管理；
2. hash 未被用户改；
3. owner 只有这个 pack；
4. source lock/receipt 更新；
5. backup 可恢复。

第一版不建议立即做 `--files`，先把 apply 做稳。

---

## 13. 测试计划

### 13.1 新增测试文件

```text
tests/test_gsd_install_cli.py
tests/test_apply.py
tests/test_component_installer.py
tests/test_source_lock_apply.py
tests/test_receipt_apply.py
tests/test_doctor_apply_readiness.py
tests/test_e2e_apply_bundled.py
```

### 13.2 GSD CLI 测试

覆盖：

- `ecc-init gsd status --json`;
- `ecc-init gsd install --dry-run --json`;
- `ecc-init gsd install --yes --json` with FakeRunner;
- install command includes runtime/scope args;
- no shell=True;
- Node missing blocks;
- Node too old blocks;
- Windows command suffix;
- project scope vs global scope.

### 13.3 Apply 测试

覆盖：

- `apply` no `--yes` is dry-run；
- `apply --yes` writes bundled files；
- apply writes state v2；
- apply writes source lock；
- apply writes receipt；
- apply can be rolled back；
- apply refuses project root mismatch；
- apply refuses unknown source；
- apply refuses unsafe target path；
- apply preserves user existing unowned files；
- apply handles user modified managed file；
- apply skips unsupported optional source；
- apply fails unsupported required source；
- apply sync-gsd if config exists；
- apply does not create GSD config if missing。

### 13.4 Component Installer 测试

覆盖：

- bundled single file projection；
- bundled directory projection；
- target path outside root rejected；
- project/global target scope；
- stack condition filtering；
- owner list；
- shared file owner；
- frontmatter preserved；
- content_version recorded。

### 13.5 E2E Bundled

三个 fixtures：

```text
tests/fixtures/projects/empty
tests/fixtures/projects/fastapi-langgraph
tests/fixtures/projects/react-vite
```

每个跑：

```text
plan
apply --yes
status
doctor
rollback
```

### 13.6 网络 E2E

保持 opt-in：

```text
ECC_INIT_NETWORK_E2E=1
```

不要在普通 CI 跑。

---

## 14. 实施阶段

## Phase A：GSD 命令语义修正

### 目标

设备级 GSD 安装和项目级 Pack 安装拆清楚。

### 任务

1. 新增 `gsd` CLI 子命令组。
2. 新增 `GsdInstallOptions`。
3. 修正 install command。
4. 修正 update command 语义。
5. `init --yes` 不再把 update 当 install。
6. `workflow status` 可保留，但建议提示使用 `gsd status`。
7. 更新 README。

### 验收

- fake runner tests 通过；
- dry-run 不执行；
- install command 有 `--claude --global`；
- 没有 shell=True；
- `init --yes` 输出设备级/项目级边界。

---

## Phase B：Apply 骨架

### 目标

`apply` 从 validate-only 变成可事务化入口，但第一批只做 dry-run 和报告结构。

### 任务

1. 新增 `src/ecc_init/apply.py`。
2. 新增 `ApplyReport`。
3. Plan 校验。
4. Project root 校验。
5. Dry-run report。
6. CLI 接入。
7. 测试。

### 验收

- `apply plan.json --dry-run --json` 结构稳定；
- 不写文件；
- 错误清晰；
- 非 `--yes` 默认 dry-run。

---

## Phase C：Bundled Component Install

### 目标

第一版真正写入项目级 bundled files。

### 任务

1. 实现 `ComponentInstaller`。
2. 支持 bundled provider。
3. 支持 file projection。
4. 支持 existing file preserve。
5. 支持 managed file update。
6. 写 state v2。
7. 写 source lock。
8. 写 receipt。
9. 支持 rollback。

### 验收

- FastAPI fixture apply 后出现对应 project skills；
- rollback 删除新建文件；
- 用户文件不覆盖；
- source lock 存在；
- receipt 存在。

---

## Phase D：sync-gsd 集成 apply

### 目标

Apply 后自动把已有 GSD config 合并。

### 任务

1. apply 增加 `--sync-gsd / --no-sync-gsd`。
2. 如果 `.planning/config.json` 存在，默认 sync。
3. 如果不存在，只写 pending or warning，不创建。
4. receipt 记录 config change。
5. rollback 恢复 config。

### 验收

- 已有 GSD config 项目 apply 后 agent_skills 增加；
- 用户显式 false 不覆盖；
- missing skill 不注入；
- GSD config 不存在时不创建。

---

## Phase E：Source Lock / Receipt / Doctor 完整化

### 目标

让用户能审计安装了什么。

### 任务

1. state/status 展示 installed packs。
2. doctor 检查 source lock。
3. doctor 检查 receipt。
4. status 展示 workflow / packs / sources。
5. README 增加 audit 示例。

### 验收

- `status --json` 能看到 packs；
- `doctor --json` 能看到 source lock；
- receipt 可用于 rollback；
- source lock 可用于 update check。

---

## Phase F：GitHubArchive Component Projection

### 目标

接入固定 commit GitHub source，但只支持显式 component。

### 任务

1. 用现有 GitHubArchiveProvider。
2. 实现 source path + projection。
3. 写 source lock。
4. 支持 offline cache。
5. hash mismatch fail。
6. ordinary CI 不跑网络。
7. fake zip tests。

### 验收

- fixed archive fixture 可安装；
- mutable ref rejected；
- zip slip rejected；
- symlink rejected；
- offline cache works；
- source lock exact commit。

---

## Phase G：Full E2E

### 目标

跑通真实用户路径。

### 场景 1：empty project

```bash
ecc-init plan . --output plan.json
ecc-init apply plan.json --yes
ecc-init status --json
ecc-init doctor --json
ecc-init rollback --operation-id <id>
```

期望：

- 只安装 project-baseline / quality-basic；
- no frontend / fastapi / rag；
- rollback 干净。

### 场景 2：FastAPI + LangGraph

期望：

- python-fastapi；
- rag-python；
- project skills；
- GSD config sync if present。

### 场景 3：React + Vite

期望：

- frontend-essential；
- react / typescript / ui skill；
- frontend lifecycle doc；
- doctor frontend detection。

### 场景 4：已有 GSD config

期望：

- apply + sync-gsd；
- 不覆盖用户 false；
- agent_skills 正确。

---

## Phase H：Release Gate

### 目标

决定是发 `0.2.0a1` 还是 `0.2.0b0`。

### 任务

1. 更新 version。
2. 更新 changelog。
3. 更新 README。
4. 更新 ARCHITECTURE。
5. 更新 MIGRATION。
6. 更新 SOURCE_POLICY。
7. 更新 e2e evidence。
8. release dry run。
9. wheel check。
10. pipx smoke。
11. GitHub Actions green。

### 验收

```bash
python -m pytest
python -m compileall -q src scripts
python scripts/release_dry_run.py
pipx install . --force
ecc-init --version
```

---

## 15. 关键实现细节

### 15.1 不要让 apply 自动安装 GSD

默认行为：

```text
apply 不安装 GSD
apply 检查 GSD status
GSD missing → warning
```

只有用户显式：

```bash
ecc-init apply plan.json --yes --install-gsd
```

才安装 GSD。

原因：

- GSD 是设备级；
- Pack 是项目级；
- 避免每个项目重复全局安装；
- 避免对全局 Claude Home 做隐式写入。

### 15.2 GSD status 的状态枚举

```text
not_installed
installed_unverified
installed_verified
blocked_environment
unknown
```

不要只有 ok/fail。

### 15.3 Apply 的状态枚举

```text
planned
dry_run
applied
failed
rolled_back
rollback_partial
blocked
```

### 15.4 Unsupported source kind 策略

```text
optional_policy + required=false → skip warning
optional_policy + required=true → fail
github_archive → supported after Phase F
external_cli → unsupported until future
npm → only workflow, not component install
bundled → supported first
```

### 15.5 init 的最终推荐行为

```bash
ecc-init init .
```

输出 plan summary。

```bash
ecc-init init . --yes
```

等价于：

```text
plan
apply
sync-gsd if possible
```

但不自动安装 GSD，除非：

```bash
ecc-init init . --yes --install-gsd
```

### 15.6 Legacy 行为

`--legacy` 暂时保留：

```bash
ecc-init init . --legacy --offline
```

但 README 要继续强调：

- legacy 是迁移兼容；
- 新用户不建议；
- 后续版本可能移除。

---

## 16. 文档更新清单

必须更新：

```text
README.md
CHANGELOG.md
ARCHITECTURE.md
MIGRATION.md
SOURCE_POLICY.md
SECURITY.md
docs/e2e/0.2.0-alpha.md
docs/internal/IMPLEMENTATION_STATUS.md
```

README 必须解释：

```text
GSD 是完整安装一次
Pack 是按项目选择性安装
init 默认 preview
apply 才写项目文件
sync-gsd 只在 GSD config 已存在时写
legacy 仅兼容
```

新增文档：

```text
docs/how-to/install-gsd.md
docs/how-to/apply-packs.md
docs/how-to/audit-and-rollback.md
```

---

## 17. Definition of Done

下一阶段完成必须满足：

1. `ecc-init gsd install --dry-run --json` 可用。
2. `ecc-init gsd install --yes --json` 使用 FakeRunner 测试通过。
3. GSD install command 明确 runtime/scope。
4. `init --yes` 不再把 update 当 install。
5. `apply` 不再是 validate-only。
6. `apply --yes` 可安装 bundled project components。
7. `apply` 写 state v2。
8. `apply` 写 source lock。
9. `apply` 写 operation receipt。
10. `rollback --operation-id` 可回滚 apply。
11. `apply` 不覆盖用户文件。
12. `apply` 对 unsupported optional source 只 warning。
13. `apply` 对 unsupported required source fail。
14. `sync-gsd` 可在 apply 后自动运行。
15. GSD config 不存在时不创建。
16. `doctor` 报告 GSD/source lock/receipt/apply readiness。
17. `status --json` 展示 workflow/packs/sources。
18. empty/FastAPI+LangGraph/React+Vite 三个 E2E fixture 通过。
19. 普通 CI 不跑网络 E2E。
20. release dry run 通过。
21. README 明确“一台设备 GSD 装一次，每个项目 Pack 初始化一次”。
22. 不 Fork、不 vendor、不复制 GSD 内部文件。
23. 不安装 optional Vercel/Anthropic/UI UX CLI 真实内容。
24. 不新增生产依赖，除非明确记录理由。
25. 所有新增命令有 JSON 输出测试。
26. 所有写操作默认 dry-run，除非 `--yes`。
27. 所有失败路径有测试。
28. Windows path tests 不退化。
29. `python -m pytest` 通过。
30. `python -m compileall -q src scripts` 通过。
31. `git diff --check` 通过。

---

## 18. 给 Codex 的启动提示

将本文件保存为仓库根目录 `CODEX_NEXT_PLAN_GSD_APPLY.md` 后，对 Codex 输入：

```text
请完整阅读 AGENTS.md、DEVELOPMENT_PLAN_CODEX.md、CODEX_NEXT_PLAN_GSD_APPLY.md、README.md、ARCHITECTURE.md、MIGRATION.md、SOURCE_POLICY.md、SECURITY.md 和 docs/internal/IMPLEMENTATION_STATUS.md，然后开始下一阶段开发。

当前目标不是继续增加新 Pack，而是打通 GSD 安装语义和 InstallPlan apply 闭环。

严格要求：
1. 不 Fork、不 vendor、不复制、不修改 GSD Core；
2. GSD Core 是完整安装的设备/runtime 级工作流内核；
3. Pack 是按项目选择性安装；
4. GSD 不应每次项目 init 都重复安装；
5. 第一批先做 GSD CLI/status/install 语义修正和 apply dry-run/report 骨架；
6. 写操作默认 dry-run，必须 --yes 才写；
7. 第一批不得使用并行写子 Agent；
8. 每个批次必须运行 targeted tests、完整 pytest、compileall、git diff --check；
9. 更新 docs/internal/IMPLEMENTATION_STATUS.md；
10. 不要把 apply 继续留成 validate-only；
11. 不要让 init --yes 继续把 workflow update 当作 GSD install；
12. 不要实现 external_cli / Anthropic / Vercel 真实安装，先完成 bundled 和固定 GitHub archive。
```

---

## 19. 最终目标图

```text
设备级，一次安装：
ecc-init gsd install --yes
        ↓
完整 GSD Core 安装到 Claude Code runtime

每个项目，一次初始化：
ecc-init plan . --output ecc-plan.json
ecc-init apply ecc-plan.json --yes
        ↓
检测技术栈
选择 Pack
安装项目 Skill
写 Source Lock
写 Receipt
写 State v2
        ↓
如果 .planning/config.json 存在：
ecc-init sync-gsd .
        ↓
agent_skills / parallelization / workflow defaults 合并

日常开发：
/gsd-new-project
/gsd-discuss-phase
/gsd-plan-phase
/gsd-execute-phase
/gsd-verify-work
/gsd-ship
```

一句话：

> GSD 是完整安装的一次性工作流内核；ecc-init 是按项目选择能力包、审计来源、同步 GSD 配置、支持回滚的管理层。
