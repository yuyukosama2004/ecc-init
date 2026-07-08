# ecc-init 0.2.0a1 修复清单：交给 Claude Code / DeepSeek V4 Pro

> 文件建议路径：仓库根目录 `CLAUDE_CODE_FIXLIST_0.2.0A1.md`  
> 执行工具：Claude Code，模型可用 DeepSeek V4 Pro  
> 目标仓库：`yuyukosama2004/ecc-init`  
> 当前基线：`0.2.0a1`  
> 任务性质：修复、硬化、用户体验收口，不是继续扩功能  
> 核心约束：不 Fork GSD，不 vendor GSD，不复制 GSD 内部 commands/agents/hooks/skills，不新增 Pack，不接入真实 external_cli / Anthropic / Vercel / UI UX Pro Max 安装。

---

## 0. 当前仓库状态判断

当前 `ecc-init 0.2.0a1` 已经完成了一个 Alpha 闭环：

```text
plan
→ apply --yes
→ 写项目 Pack 文件
→ 写 .claude/ecc-sources.lock.json
→ 写 .claude/ecc-init-state.json
→ 写 operation receipt
→ status / doctor 审计
→ rollback --operation-id
```

目前不应该继续大规模扩展架构，而应该先修这些问题：

1. GSD 环境检查和官方要求不一致；
2. doctor 对未 apply 的干净项目过于严格；
3. apply 成功/部分成功/跳过组件的状态表达不够细；
4. human CLI 输出不够可操作，尤其 operation_id / rollback 提示不明显；
5. 测试运行方式依赖 `PYTHONPATH=src`，普通 `python -m pytest` 仍会失败；
6. GSD runtime/scope 选项需要和上游 installer 实际能力重新核对；
7. apply/install-gsd 的设备级副作用需要更明确地提示和记录；
8. 文档需要把 Alpha 可用边界写得更直白。

---

## 1. 执行总约束

### 1.1 必须先运行基线

开始改代码前，先运行并记录：

```bash
git status --short
git branch --show-current
git log -5 --oneline
python -m pytest
python -m compileall -q src scripts
git diff --check
```

如果 `python -m pytest` 因为 src-layout 导致 `ModuleNotFoundError: No module named 'ecc_init'`，不要忽略。这个本身就是本清单的修复项之一。可以临时用：

```bash
$env:PYTHONPATH="src"
python -m pytest
```

但最终要修到普通测试入口也能稳定运行，或者在项目配置中明确 pytest 的 pythonpath。

### 1.2 本批次禁止事项

本批次不要做：

- 不新增新 Pack；
- 不新增真实第三方 source installer；
- 不做 UI UX Pro Max / Vercel / Anthropic 真实安装；
- 不做 source update apply；
- 不做 remove 文件级删除；
- 不创建 `.planning/config.json`；
- 不让 `init` 每次自动安装 GSD；
- 不改 GSD Core 源码；
- 不把 GSD Core 文件复制进本仓库；
- 不删除用户文件；
- 不覆盖用户已有配置；
- 不使用并行写子 Agent。

### 1.3 子 Agent 限制

本任务以主 Agent 为主。

允许：

```text
只读 Explorer：最多 1
只读 Reviewer：最多 1
并行 Write Worker：0
嵌套深度：1
```

如果使用 Reviewer，必须只读审查，不直接改代码。

---

## 2. P0 必修问题

---

# P0-01：修正 GSD Node/npm 最低版本检查

## 问题

当前 `src/ecc_init/workflows/gsd.py` 里：

```python
MIN_NODE_VERSION = (18, 0, 0)
```

但 pinned 的 `@opengsd/gsd-core@1.6.1` 上游 `package.json` 要求：

```json
"engines": {
  "node": ">=22.0.0",
  "npm": ">=10.0.0"
}
```

当前代码只检查 Node 18+，也没有解析 npm 版本。这会导致用户在 Node 18/20 环境下通过 `ecc-init gsd status/install` 的本地检查，但实际 GSD installer 可能失败。

## 需要修改

文件：

```text
src/ecc_init/workflows/gsd.py
tests/test_workflows.py
tests/test_gsd_install_cli.py
README.md
docs/how-to/install-gsd.md
```

任务：

1. 将 GSD 环境要求改为：
   ```python
   MIN_NODE_VERSION = (22, 0, 0)
   MIN_NPM_VERSION = (10, 0, 0)
   ```

2. `environment_checks()` 同时检查：
   - node present；
   - npm present；
   - npx present；
   - node version >= 22；
   - npm version >= 10。

3. `npx` 没有单独 version 要求也要 present。

4. dry-run 行为：
   - dry-run 不执行 version subprocess；
   - dry-run check detail 应显示 `not checked during dry-run`；
   - 但 message 应写清楚 Node.js 22+ / npm 10+。

5. 非 dry-run：
   - node 版本不满足 → `blocked_environment`；
   - npm 版本不满足 → `blocked_environment`；
   - npm/npx 缺失 → `blocked_environment`。

6. README 和 install-gsd how-to 必须把要求改成 Node 22+ / npm 10+。

## 验收测试

新增或修改测试：

```text
test_gsd_install_blocks_when_node_too_old
test_gsd_install_blocks_when_npm_too_old
test_gsd_install_blocks_when_npm_missing
test_gsd_install_blocks_when_npx_missing
test_gsd_install_dry_run_does_not_execute_versions
```

验收：

```bash
python -m pytest tests/test_workflows.py tests/test_gsd_install_cli.py
```

---

# P0-02：修正 `apply --yes` 的“部分安装也算成功”问题

## 问题

现在 `ComponentInstaller` 遇到这些情况时会 warning，然后继续：

```text
preserved existing unowned file
preserved user-modified managed file
skipped non-project component
skipped unsupported optional component
```

这本身是安全的，但 `apply_install_plan()` 最终仍可能：

```text
status = "applied"
result = "success"
packs = 所有 plan.packs
```

这会造成一个问题：

> 某个 Pack 的关键 Skill 没有写进去，但 state/receipt/status 仍然显示 Pack 已安装。

特别是：

- existing unowned file 被 preserve；
- user-modified managed file 被 preserve；
- non-project component 被 skip；
- optional component 被 skip；
- global component 被 skip。

这些情况不应该和“完整安装成功”混在一起。

## 需要修改

文件：

```text
src/ecc_init/packs/installer.py
src/ecc_init/apply.py
src/ecc_init/app.py
tests/test_apply.py
tests/test_e2e_apply_bundled.py
```

### 目标状态枚举

建议引入：

```text
applied
applied_with_warnings
partial
failed
dry_run
blocked
```

或者至少：

```text
applied
partial
failed
```

### ComponentInstallReport 增强

在 `ComponentInstallReport` 增加：

```python
files_skipped: list[SkippedComponent]
required_skipped: list[SkippedComponent]
optional_skipped: list[SkippedComponent]
non_project_skipped: list[SkippedComponent]
preserved_files: list[SkippedComponent]
```

每个 skipped item 至少包含：

```json
{
  "component_id": "...",
  "source_id": "...",
  "target_path": "...",
  "reason": "...",
  "required": true
}
```

### ApplyReport 增强

`ApplyReport.to_dict()` 增加：

```json
{
  "files_skipped": [],
  "components_skipped": [],
  "packs_applied": [],
  "packs_partial": [],
  "packs_skipped": []
}
```

### Pack 状态

不要再简单把所有 `plan.packs` 都写成已安装。

建议 state v2：

```json
"packs": {
  "python-fastapi": {
    "version": 1,
    "status": "applied",
    "components_applied": ["skill-python-patterns", "skill-fastapi-patterns"],
    "components_skipped": []
  },
  "quality-basic": {
    "version": 1,
    "status": "partial",
    "components_applied": ["project-overview"],
    "components_skipped": ["global-reviewer-skill"]
  }
}
```

如果为了兼容暂时不能改变结构，可以先新增：

```json
"pack_status": {}
```

但不要破坏现有读取逻辑。

### Receipt 结果

Receipt 的 `result` 不应该永远是 success。

建议：

```text
success
partial_success
failed
rolled_back
partial_rollback
```

如果存在 required component 被 preserve/skip，应该至少是 `partial_success`，甚至按策略视为 blocker。

## 验收测试

新增/修改：

```text
test_apply_preserved_unowned_required_component_marks_partial
test_apply_user_modified_managed_file_marks_partial
test_apply_receipt_result_partial_when_required_component_skipped
test_status_reports_partial_pack
test_doctor_warns_on_partial_pack
```

现有测试 `test_apply_preserves_existing_unowned_files` 不应只检查 warning，还要检查状态不是单纯 `applied + success`。

---

# P0-03：修正 `doctor` 对未初始化干净项目过于严格的问题

## 问题

当前 `doctor()` 把这些检查作为失败：

```text
Installed Packs: none
Project source lock missing
Latest apply receipt missing
GSD runtime not_installed
```

这对“已安装项目审计”合理，但对一个新项目来说，第一次运行 doctor 前没有 Pack、没有 Source Lock、没有 Receipt 很正常。

现在用户会看到一堆 FAIL，容易误以为项目坏了。

## 需要修改

文件：

```text
src/ecc_init/app.py
src/ecc_init/cli.py
tests/test_app.py
tests/test_lifecycle_cli.py
README.md
docs/how-to/audit-and-rollback.md
```

## 方案

增加 doctor 模式：

```bash
ecc-init doctor . --mode preflight
ecc-init doctor . --mode audit
```

默认建议：

```text
mode = preflight
```

### preflight 语义

适合第一次 apply 前：

- Python/Git/目录不可写：FAIL
- GSD missing：WARN
- Installed Packs none：WARN
- Source Lock missing：WARN
- Receipt missing：WARN
- Apply readiness blockers：FAIL
- Apply readiness warnings：WARN

### audit 语义

适合 apply 后审计：

- Installed Packs none：FAIL
- Source Lock missing：FAIL
- Receipt missing：FAIL
- Plan/apply drift：WARN/FAIL，视严重度
- GSD runtime missing：WARN 或 FAIL，依据是否要求 runtime。

### JSON 输出

`doctor --json` 增加：

```json
{
  "mode": "preflight",
  "summary": {
    "PASS": 0,
    "WARN": 0,
    "FAIL": 0
  }
}
```

## 验收测试

新增：

```text
test_doctor_preflight_clean_project_warns_not_fails
test_doctor_audit_clean_project_fails_missing_audit_artifacts
test_doctor_after_apply_audit_passes
```

---

# P0-04：修正普通 `python -m pytest` 失败的问题

## 问题

实施记录显示，裸命令：

```bash
python -m pytest
```

会因为 src-layout 导致：

```text
ModuleNotFoundError: No module named 'ecc_init'
```

现在测试依赖：

```bash
PYTHONPATH=src
```

或者 editable install。

这对 Claude Code / Codex / 普通贡献者都不友好。

## 需要修改

文件：

```text
pyproject.toml
docs/internal/IMPLEMENTATION_STATUS.md
README.md
```

## 推荐方案

在 `pyproject.toml` 里配置 pytest pythonpath。

可选：

```toml
[tool.pytest.ini_options]
addopts = "-q"
testpaths = ["tests"]
pythonpath = ["src"]
```

如果当前 pytest 版本不支持 `pythonpath`，则改用 `pytest.ini`：

```ini
[pytest]
testpaths = tests
addopts = -q
pythonpath = src
```

优先用 `pyproject.toml`，避免新文件。

## 验收

必须能直接运行：

```bash
python -m pytest
```

不再要求用户手动设置 `PYTHONPATH=src`。

并保留：

```bash
python -m compileall -q src scripts
git diff --check
```

---

## 3. P1 应修问题

---

# P1-01：让 human CLI 输出 operation_id / rollback 命令

## 问题

当前 `apply --json` 会输出 `operation_id`，但 human 输出只显示：

```text
Plan project:
Workflow:
Packs:
Status:
warnings/errors
```

用户如果不用 JSON，很难知道怎么 rollback。

`init --yes` human 输出也没有明显展示 operation id。

## 需要修改

文件：

```text
src/ecc_init/cli.py
tests/test_lifecycle_cli.py
tests/test_apply.py
README.md
docs/how-to/audit-and-rollback.md
```

## 目标输出

`ecc-init apply ecc-plan.json --yes` 成功后 human 输出至少包含：

```text
Status: applied
Operation: apply-...
Backup: ...
Files written: 6
Source lock: .claude/ecc-sources.lock.json
Receipt: ~/.ecc-init/operations/<operation-id>/receipt.json

Rollback:
  ecc-init rollback . --operation-id <operation-id>
```

`init --yes` 也要显示：

```text
Apply operation: ...
Rollback:
  ecc-init rollback . --operation-id ...
```

## 验收测试

新增：

```text
test_apply_human_output_includes_operation_id_and_rollback_hint
test_init_yes_human_output_includes_apply_operation_id
```

---

# P1-02：明确 `apply --install-gsd --yes` 的设备级副作用

## 问题

`apply --install-gsd --yes` 可以调用 GSD installer，但 GSD 是设备/runtime 级安装，不属于项目 rollback。

这件事必须在 CLI 输出、JSON 和文档里非常明确，否则用户可能以为：

```text
rollback --operation-id
```

也会卸载 GSD Core。

## 需要修改

文件：

```text
src/ecc_init/apply.py
src/ecc_init/cli.py
README.md
docs/how-to/install-gsd.md
docs/how-to/audit-and-rollback.md
tests/test_apply.py
tests/test_gsd_install_cli.py
```

## 行为要求

当 `--install-gsd` 被使用时：

1. human 输出必须显示：
   ```text
   GSD Core install is device/runtime-level and is not covered by project rollback.
   ```

2. JSON 输出增加：
   ```json
   "device_side_effects": [
     {
       "type": "gsd-install",
       "rollback_supported": false,
       "message": "..."
     }
   ]
   ```

3. Receipt 里可以记录 workflow install status，但不要暗示项目 rollback 能恢复设备级 GSD。

## 验收测试

```text
test_apply_install_gsd_json_reports_device_side_effect_not_rollbackable
test_apply_install_gsd_human_output_warns_device_scope
```

---

# P1-03：核对并限制 GSD runtime flags

## 问题

当前支持：

```text
auto → --claude
claude → --claude
codex → --codex
cursor → --cursor
```

但必须确认 pinned `@opengsd/gsd-core@1.6.1` installer 是否真的支持这些 flags。

如果上游暂时只稳定支持 Claude，那么 `codex/cursor` 不应该出现在稳定 CLI choices 里，至少应该标记 experimental。

## 需要修改

文件：

```text
src/ecc_init/workflows/gsd.py
src/ecc_init/cli.py
tests/test_gsd_install_cli.py
docs/how-to/install-gsd.md
SOURCE_POLICY.md
```

## 要求

1. 用下面方式之一确认上游：
   ```bash
   npx -y @opengsd/gsd-core@1.6.1 --help
   ```
   或读取上游 installer 源码。

2. 如果 `--codex` / `--cursor` 支持不明确：
   - CLI choices 先只保留 `claude`；
   - 或将 `codex/cursor` 标记为 experimental，并要求 `--experimental-runtime`。

3. 文档不要暗示所有 runtime 都已经稳定可用。

## 验收测试

```text
test_gsd_cli_rejects_unsupported_runtime
test_gsd_cli_experimental_runtime_requires_flag
```

如果确认上游稳定支持 codex/cursor，则改为测试 help/源码约束，并记录依据。

---

# P1-04：GSD status marker 检测要更稳

## 问题

当前 `_has_verified_markers()` 通过 glob 检测：

```text
commands/gsd*
commands/gsd/*
agents/gsd*
skills/gsd-*
hooks/gsd*
```

这可能和 GSD installer 的真实安装布局有偏差。

如果 marker 检测过窄，安装成功后会一直显示 `installed_unverified`。  
如果 marker 检测过宽，可能误判用户自己建的文件为 GSD。

## 需要修改

文件：

```text
src/ecc_init/workflows/gsd.py
tests/test_workflows.py
docs/how-to/install-gsd.md
```

## 要求

1. 明确不同 scope 的 expected install root：
   - Claude global；
   - Claude local/project；
   - 未来 runtime。

2. 增加 marker 检测测试：
   ```text
   test_gsd_status_verified_when_expected_command_marker_exists
   test_gsd_status_not_verified_for_unrelated_files
   test_gsd_status_project_scope_uses_project_claude_root
   ```

3. 如果无法可靠判断，保留 `installed_unverified`，但输出必须告诉用户：
   ```text
   Installer succeeded, but ecc-init could not verify GSD runtime artifacts.
   Run a GSD command in Claude Code to confirm.
   ```

---

# P1-05：`status --json` 和 state 需要表达 partial / drift

## 问题

现在 `status` 已经有 installed/planned/source lock/receipt/readiness，但 Pack 维度太粗。

如果某个 Pack：

- 只写了一部分 components；
- 有 required component 被 preserve；
- 有 optional component 被 skip；
- 有 global component skipped；
- user modified managed file 被保留；

`status` 应该能显示：

```text
pack: partial
reason: ...
```

## 需要修改

文件：

```text
src/ecc_init/app.py
src/ecc_init/apply.py
src/ecc_init/packs/installer.py
tests/test_app.py
tests/test_apply.py
```

## JSON 目标

```json
"packs": {
  "installed": {
    "python-fastapi": {
      "status": "applied",
      "components_applied": [],
      "components_skipped": []
    },
    "quality-basic": {
      "status": "partial",
      "components_applied": [],
      "components_skipped": [
        {
          "component_id": "...",
          "reason": "non-project component skipped in current apply batch"
        }
      ]
    }
  },
  "planned": []
}
```

## human 输出

```text
Installed Packs:
- python-fastapi: applied
- quality-basic: partial
```

---

# P1-06：`apply --dry-run` 的 Source Lock 预览要更准确

## 问题

Dry-run 当前的 `sources_locked` 是按 resolved components 的 source_id 生成 planned 列表。

但真实 apply 会只 lock 实际写入文件的 source。

这会导致 dry-run 预览和 apply 结果不完全一致，尤其在：

- optional source skip；
- existing unowned preserve；
- non-project component skip；
- unsupported source skip。

## 建议

Dry-run 报告拆成：

```json
"sources_planned": [],
"sources_would_lock": [],
"sources_maybe_skipped": []
```

如果暂时无法精确预测 `sources_would_lock`，就明确：

```json
"sources_locked": [],
"sources_planned": []
```

不要让用户以为 dry-run 已经能准确给出最终 lock。

## 测试

```text
test_apply_dry_run_distinguishes_sources_planned_from_sources_locked
```

---

# P1-07：把 `--skip-gsd-check` 标记为 CI/测试辅助选项

## 问题

`--skip-gsd-check` 很适合 E2E 和 CI，但普通用户容易误用，导致不知道自己有没有装 GSD。

## 需要修改

文件：

```text
src/ecc_init/cli.py
README.md
docs/how-to/apply-packs.md
```

## 要求

1. help 文案改成：
   ```text
   skip GSD runtime status check; intended for CI/tests or when you intentionally manage GSD separately
   ```

2. human 输出加 warning：
   ```text
   GSD runtime check was skipped; ecc-init did not verify that GSD Core is installed.
   ```

3. JSON 输出：
   ```json
   "workflow_status": {
     "status": "skipped"
   }
   ```

现在 `skip_gsd_check` 时 result 是 None，用户不够直观。

---

## 4. P2 可延后问题

---

# P2-01：GitHub archive 只支持单文件 projection，文档要更明确

当前支持固定 commit 单文件 projection，这是合理的 Alpha 范围。

但文档需要明确：

```text
支持：显式 fixed commit + project-scope single-file component
不支持：directory projection、默认 Pack 远程安装、真实 source update
```

不要让用户以为 ECC/Vercel/Anthropic 都已经能完整远程安装。

---

# P2-02：`remove --pack X --files --yes` 暂时不要做，但要列 roadmap

当前 remove 只清 GSD config binding，不删 Skill 文件，这是安全的。

只需要文档说明：

```text
remove 不删除 Skill 文件
remove 不卸载 GSD Core
文件级 remove 会在未来版本实现
```

如果要加 roadmap，必须写清四个前置条件：

1. 文件由 ecc-init 管理；
2. 文件 hash 未被用户改；
3. owner 只有这个 pack；
4. receipt/backup 可回滚。

---

# P2-03：真实项目人工验收清单

新增一份文档：

```text
docs/e2e/manual-alpha-smoke.md
```

内容包括：

```bash
ecc-init gsd status
ecc-init gsd install --dry-run
ecc-init plan . --output ecc-plan.json
ecc-init apply ecc-plan.json --yes
ecc-init status
ecc-init doctor
ecc-init rollback . --operation-id <id>
```

至少覆盖：

- empty；
- FastAPI/LangGraph；
- React/Vite；
- 已有 `.planning/config.json` 的 GSD 项目。

---

## 5. 本批次推荐执行顺序

### Batch 1：环境和测试入口修复

范围：

- P0-01 Node/npm 版本检查；
- P0-04 普通 pytest 修复。

命令：

```bash
python -m pytest tests/test_workflows.py tests/test_gsd_install_cli.py
python -m pytest
python -m compileall -q src scripts
git diff --check
```

### Batch 2：apply partial 状态修复

范围：

- P0-02；
- P1-05；
- P1-06。

命令：

```bash
python -m pytest tests/test_apply.py tests/test_app.py tests/test_e2e_apply_bundled.py
python -m pytest
python -m compileall -q src scripts
git diff --check
```

### Batch 3：doctor UX 修复

范围：

- P0-03；
- P1-07。

命令：

```bash
python -m pytest tests/test_app.py tests/test_lifecycle_cli.py
python -m pytest
python -m compileall -q src scripts
git diff --check
```

### Batch 4：CLI 输出和文档收口

范围：

- P1-01；
- P1-02；
- P1-03；
- P1-04；
- P2 文档项。

命令：

```bash
python -m pytest tests/test_gsd_install_cli.py tests/test_workflows.py tests/test_apply.py tests/test_lifecycle_cli.py tests/test_security_release.py
python -m pytest
python -m compileall -q src scripts
git diff --check
```

---

## 6. 完成标准

本修复清单完成时，必须满足：

1. `python -m pytest` 不再因为 `ModuleNotFoundError` 失败。
2. GSD 环境检查使用 Node 22+ / npm 10+。
3. npm 缺失或版本过低会阻塞真实 install/update。
4. `apply --yes` 对部分安装有明确状态，不再把所有 warning 都包装成纯 success。
5. state / status / receipt 能表达 pack partial。
6. `doctor` 支持 preflight/audit 或等价模式，干净未 apply 项目不出现误导性失败。
7. human `apply` / `init --yes` 输出 operation id 和 rollback 命令。
8. `--install-gsd` 的设备级副作用在 human/JSON/doc 中明确不可由项目 rollback 回滚。
9. `--skip-gsd-check` 明确是测试/CI/高级选项。
10. GSD runtime flags 已核对，不支持的 runtime 不暴露为稳定选项。
11. GSD marker 检测有测试。
12. 所有新增行为有 JSON 输出测试。
13. README 和 how-to 文档同步更新。
14. `python -m pytest` 通过。
15. `python -m compileall -q src scripts` 通过。
16. `git diff --check` 通过。

---

## 7. 给 Claude Code / DeepSeek V4 Pro 的启动提示

把本文件放到仓库根目录后，在 Claude Code 中输入：

```text
请完整阅读 CLAUDE_CODE_FIXLIST_0.2.0A1.md、AGENTS.md、README.md、ARCHITECTURE.md、SOURCE_POLICY.md、SECURITY.md、docs/internal/IMPLEMENTATION_STATUS.md，以及当前相关源码。

本批次只做修复和硬化，不做新功能扩张。优先按 P0 顺序执行：
1. 修正 GSD Node/npm 环境要求；
2. 修正普通 python -m pytest 失败；
3. 修正 apply partial 状态；
4. 修正 doctor 对干净项目过于严格的问题。

不要新增 Pack，不要接入真实第三方 installer，不要复制或修改 GSD Core，不要使用并行写子 Agent。每个批次结束必须运行 targeted tests、python -m pytest、python -m compileall -q src scripts、git diff --check，并更新 docs/internal/IMPLEMENTATION_STATUS.md。
```
