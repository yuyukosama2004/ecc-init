# ecc-init 0.2.0a1 第二轮修复清单：Alpha 收口问题

> 文件建议路径：仓库根目录 `CLAUDE_CODE_FIXLIST_ROUND2_0.2.0A1.md`  
> 执行工具：Claude Code，可使用 DeepSeek V4 Pro  
> 目标仓库：`yuyukosama2004/ecc-init`  
> 当前基线：`0.2.0a1`  
> 任务性质：继续修复与硬化，不扩新功能  
> 核心目标：修掉当前 Alpha 内测前剩余的用户体验、状态一致性和审计可靠性问题。  
> 非目标：不新增 Pack，不新增真实第三方 installer，不做 source update apply，不做 remove 文件级删除，不 Fork / vendor / 修改 GSD Core。

---

## 0. 当前状态结论

当前仓库已经比上一轮明显进步：

- GSD Node/npm 要求已经改成 Node 22+ / npm 10+；
- `python -m pytest` 已经通过 `pyproject.toml` 配置 `pythonpath = ["src"]`；
- GSD runtime flags 已经收窄到稳定的 `auto / claude`；
- `doctor` 已经支持 `preflight / audit` 模式；
- `apply` 已经有 partial 状态、`files_skipped`、`packs_applied / packs_partial / packs_skipped`；
- human `apply` 输出已经有 operation id 和 rollback hint；
- `--skip-gsd-check` 文案已经改为 CI/测试/高级选项；
- `apply --install-gsd` 已经有 device side effects 提示。

但是仍有 5 个需要收口的问题：

1. `init --yes` 的 human 输出仍没有 operation id / backup id / rollback 命令；
2. Pack 的 `applied / partial / skipped` 状态没有持久化进 `.claude/ecc-init-state.json`；
3. `partial` 的退出码和语义还不够细，容易把“轻微 warning”和“关键组件未安装”混在一起；
4. GSD marker 检测仍可能误判 unrelated files；
5. `doctor` 的 PASS/WARN/FAIL 仍依赖 hard-coded index，后续很容易错位。

本轮只修这 5 个问题。

---

## 1. 执行约束

### 1.1 开始前必须运行

```bash
git status --short
git branch --show-current
git log -5 --oneline
python -m pytest
python -m compileall -q src scripts
git diff --check
```

如果基线有失败，先记录在：

```text
docs/internal/IMPLEMENTATION_STATUS.md
```

不得带着未解释的基线失败继续改。

### 1.2 本轮禁止事项

不要做：

- 不新增 Pack；
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

本轮以主 Agent 为主。

允许：

```text
只读 Reviewer：最多 1
只读 Explorer：最多 1
并行 Write Worker：0
嵌套深度：1
```

---

# P0-01：补齐 `init --yes` human 输出的 operation / rollback 提示

## 问题

当前 `ecc-init apply ... --yes` 的 human 输出已经会显示：

```text
Operation: ...
Backup: ...
Rollback:
  ecc-init rollback . --operation-id ...
```

但是 `ecc-init init . --yes` 的 human 输出仍然只显示大概状态：

```text
GSD init separates device-level GSD Core install from project-level Pack apply.
Project: ...
GSD install: ...
Apply status: ...
```

它没有直接显示：

- apply operation id；
- backup id；
- rollback 命令；
- source lock；
- receipt 位置；
- files written 数量；
- partial 状态下哪些 Pack partial。

用户通过 `init --yes` 走最常用路径时，反而不知道怎么回滚。

## 需要修改

文件：

```text
src/ecc_init/cli.py
tests/test_lifecycle_cli.py
tests/test_apply.py
README.md
docs/how-to/audit-and-rollback.md
```

## 具体要求

### human 输出

`ecc-init init . --yes` 成功或 partial 后至少输出：

```text
GSD init separates device-level GSD Core install from project-level Pack apply.
Project: <project>
GSD install: not requested | installed_verified | installed_unverified | blocked_environment
Apply status: applied | applied_with_warnings | partial | failed
Apply operation: <operation-id>
Backup: <backup-id>
Files written: <n>
Files skipped: <n>
Source lock: .claude/ecc-sources.lock.json
Receipt: ~/.ecc-init/operations/<operation-id>/receipt.json

Rollback:
  ecc-init rollback . --operation-id <operation-id>
```

如果 `apply_report.operation_id` 为空，则不要打印 rollback 命令。

### JSON 输出

JSON 目前已有 `apply` 对象，保留即可。不要破坏现有 JSON schema。

### partial 输出

如果 `apply_report.packs_partial` 非空，human 输出应增加：

```text
Partial Packs:
- <pack-id>
```

如果 `apply_report.files_skipped` 非空，输出：

```text
Skipped components: <n>
```

不要把完整 JSON dump 到 human 输出中。

## 验收测试

新增或修改：

```text
test_init_yes_human_output_includes_apply_operation_id
test_init_yes_human_output_includes_rollback_hint
test_init_yes_human_output_includes_partial_summary
```

命令：

```bash
python -m pytest tests/test_lifecycle_cli.py tests/test_apply.py
```

---

# P0-02：把 Pack 状态持久化到 `.claude/ecc-init-state.json`

## 问题

当前 `ApplyReport` 已经有：

```text
packs_applied
packs_partial
packs_skipped
```

`status` 也会从 `managed_files` 和 registry 推导 Pack 状态。

但是 `_write_project_state()` 仍然只写：

```json
"packs": {
  "python-fastapi": {"version": 1}
}
```

这意味着：

- state 里没有保存 Pack 的真实状态；
- registry 以后变化时，旧项目状态可能被重新解释；
- `status` 只能临时推导，不是读取安装事实；
- receipt 有 partial_success，但 state 不知道哪个 Pack partial；
- 用户看 `.claude/ecc-init-state.json` 无法知道安装是否完整。

## 需要修改

文件：

```text
src/ecc_init/apply.py
src/ecc_init/app.py
tests/test_apply.py
tests/test_app.py
tests/test_e2e_apply_bundled.py
```

## 目标 state v2 结构

`_write_project_state()` 应写入：

```json
"packs": {
  "python-fastapi": {
    "version": 1,
    "status": "applied",
    "components_applied": [
      "skill-python-patterns",
      "skill-fastapi-patterns"
    ],
    "components_skipped": []
  },
  "quality-basic": {
    "version": 1,
    "status": "partial",
    "components_applied": [
      "project-overview",
      "development-log"
    ],
    "components_skipped": [
      {
        "component_id": "global-code-review",
        "reason": "non-project scope (global) not supported in current apply batch",
        "required": true
      }
    ]
  }
}
```

### 兼容要求

现有旧 state：

```json
"packs": {
  "python-fastapi": {"version": 1}
}
```

仍然要能读取。

`project_status()` 的 `_pack_summary()` 应优先读取 state 中的：

```text
status
components_applied
components_skipped
```

如果旧 state 没有这些字段，再 fallback 到 managed_files 推导。

### Apply 需要传入状态

当前 `_write_project_state()` 参数只有：

```python
files_written
locks
workflow_status
```

需要改成可接收：

```python
install_report
packs_applied
packs_partial
packs_skipped
```

或者直接接收一个 `pack_status` dict。

建议新增 helper：

```python
def _build_pack_state(plan, registry, install_report) -> dict[str, Any]:
    ...
```

### 状态规则

- 有 written 且无 skipped：`applied`
- 有 written 且有 skipped：`partial`
- 无 written 且有 skipped：`skipped`
- 无 expected components：`declaration_only`

对于 skipped component，保留：

```text
component_id
source_id
target_path
reason
required
```

## 验收测试

新增或修改：

```text
test_apply_state_records_pack_applied_status
test_apply_state_records_pack_partial_status
test_status_prefers_persisted_pack_status
test_status_falls_back_for_legacy_pack_state
test_e2e_apply_bundled_state_pack_status
```

命令：

```bash
python -m pytest tests/test_apply.py tests/test_app.py tests/test_e2e_apply_bundled.py
```

---

# P0-03：细化 partial / applied_with_warnings 的语义和退出码

## 问题

当前 `_print_apply()` 的返回码：

```python
return 0 if report.status in {"dry_run", "applied"} and not report.errors else 4
```

也就是说只要 status 是 `partial`，CLI 就返回 4。

这对“关键组件没装上”合理，但对下面情况可能太严格：

- optional component skip；
- non-project global component skip；
- GSD runtime missing warning；
- GSD config not initialized warning；
- source lock dry-run 不确定。

这些并不一定代表项目级 apply 失败。

## 需要修改

文件：

```text
src/ecc_init/packs/installer.py
src/ecc_init/apply.py
src/ecc_init/cli.py
tests/test_apply.py
tests/test_lifecycle_cli.py
```

## 建议状态语义

引入或规范以下状态：

```text
dry_run
applied
applied_with_warnings
partial
failed
blocked
```

### applied

所有 required project components 写入成功，没有 skipped required project component。

退出码：`0`

### applied_with_warnings

项目级 required components 成功，但存在非阻塞 warning，例如：

- unsupported optional component skipped；
- non-project global component skipped；
- GSD runtime missing；
- GSD config not initialized；
- dry-run 不确定项。

退出码：`0`

### partial

存在 required project component 被 skip/preserve，或者用户修改导致关键文件未写入。

退出码：`4`

### failed

写入失败、校验失败、rollback 后失败。

退出码：`4`

### blocked

plan 校验失败、project root mismatch、环境 blocker。

退出码：`4`

## 需要调整的逻辑

当前 `ComponentInstallReport.has_required_skipped` 排除了 non-project scope，这个方向可以保留，但还要更明确地区分：

```python
has_blocking_skipped
has_non_blocking_skipped
```

建议：

```python
@property
def has_blocking_skipped(self) -> bool:
    return any(
        item.required
        and "non-project scope" not in item.reason
        for item in self.files_skipped
    )

@property
def has_non_blocking_skipped(self) -> bool:
    return bool(self.files_skipped) and not self.has_blocking_skipped
```

`apply_install_plan()`：

```python
if errors:
    status = "failed"
elif install_report.has_blocking_skipped:
    status = "partial"
    receipt_result = "partial_success"
elif warnings or install_report.has_non_blocking_skipped:
    status = "applied_with_warnings"
    receipt_result = "success"
else:
    status = "applied"
    receipt_result = "success"
```

CLI exit code：

```python
success_statuses = {"dry_run", "applied", "applied_with_warnings"}
return 0 if report.status in success_statuses and not report.errors else 4
```

## 验收测试

新增或修改：

```text
test_apply_non_project_required_component_is_applied_with_warnings_exit_zero
test_apply_optional_skip_is_applied_with_warnings_exit_zero
test_apply_preserved_required_project_component_is_partial_exit_four
test_apply_status_applied_with_warnings_receipt_success
test_apply_status_partial_receipt_partial_success
```

命令：

```bash
python -m pytest tests/test_apply.py tests/test_lifecycle_cli.py
```

---

# P0-04：硬化 GSD marker 检测，避免 unrelated files 误判

## 问题

当前 `_has_verified_markers()` 会根据这些 pattern 判断 GSD installed：

```text
.planning
commands/gsd*
agents/gsd*
skills/gsd-*
hooks/gsd*
```

风险：

- 用户自己创建的 `commands/gsd-demo.md` 可能被误判；
- project scope 下 `.planning` 不一定代表 GSD Core runtime 安装完成；
- global scope 下 `.planning` 的意义也不明确；
- marker 过宽可能把 unrelated files 识别为 installed_verified。

## 需要修改

文件：

```text
src/ecc_init/workflows/gsd.py
tests/test_workflows.py
docs/how-to/install-gsd.md
```

## 建议方案

### Claude global scope

不要用 `.planning` 作为 global verified marker。

至少要求命中较明确的 GSD artifact，例如：

```text
commands/gsd-new-project*
commands/gsd-discuss-phase*
commands/gsd-plan-phase*
commands/gsd-execute-phase*
commands/gsd-verify-work*
commands/gsd-ship*
```

或者如果上游实际布局不同，则以当前 pinned GSD installer 产物为准。

### Claude project/local scope

`.planning/config.json` 只能表示项目已初始化 GSD 配置，不能单独证明 GSD Core runtime installed。

建议 status 分开：

```text
runtime_artifacts_verified
project_config_present
```

如果只发现 `.planning/config.json`：

```text
status = installed_unverified 或 project_config_present
```

不要直接 `installed_verified`。

### 输出

如果 installer command 成功但 marker 不稳定：

```text
installed_unverified
warning: Installer succeeded, but ecc-init could not verify GSD runtime artifacts. Run a GSD command in Claude Code to confirm.
```

这部分当前已经有，保留即可。

## 验收测试

新增：

```text
test_gsd_status_not_verified_for_unrelated_gsd_named_file
test_gsd_status_global_verified_for_known_gsd_command_marker
test_gsd_status_project_config_alone_not_runtime_verified
test_gsd_install_success_unverified_message_is_actionable
```

命令：

```bash
python -m pytest tests/test_workflows.py tests/test_gsd_install_cli.py
```

---

# P0-05：重构 doctor severity，不要靠 hard-coded index

## 问题

当前 `_doctor_payload()` 用：

```python
hard_fail_indexes = {0, 2, 3, 4, 5}
```

然后通过 index 判断失败是 FAIL 还是 WARN。

这很脆：

- 后续在 doctor() 中插入检查项会导致 index 错位；
- preflight/audit 模式下严重度规则难维护；
- JSON 输出无法知道某项为什么是 WARN 或 FAIL；
- 测试也难覆盖长期稳定性。

## 需要修改

文件：

```text
src/ecc_init/app.py
src/ecc_init/cli.py
tests/test_app.py
tests/test_lifecycle_cli.py
```

## 推荐结构

新增：

```python
@dataclass(frozen=True)
class DoctorCheck:
    check_id: str
    label: str
    ok: bool
    detail: str
    severity_if_failed: str = "fail"  # "fail" | "warn"
```

`doctor()` 返回：

```python
list[DoctorCheck]
```

如果为了兼容暂时不能改返回类型，可新增：

```python
doctor_checks(...)
```

然后让旧 `doctor()` 包一层。

### severity 规则

preflight：

```text
Python 版本：fail
Git 三方合并：warn
ecc-init 数据目录：fail
Claude 配置目录：fail
当前项目目录：fail
内置清单：fail
GSD config bridge：pass
GSD runtime missing：warn
Installed Packs none：warn
Project source lock missing：warn
Latest apply receipt missing：warn
Apply readiness blockers：fail
Plan/apply consistency not_applied：pass
```

audit：

```text
GSD runtime missing：warn 或 fail，按当前设计决定
Installed Packs none：fail
Project source lock missing：fail
Latest apply receipt missing：fail
Plan/apply consistency drift：warn
Apply readiness blockers：fail
```

### JSON 输出

每项输出：

```json
{
  "check_id": "doctor:gsd-runtime",
  "label": "GSD runtime",
  "status": "WARN",
  "ok": false,
  "severity_if_failed": "warn",
  "detail": "not_installed"
}
```

不要再靠 index 生成 check_id。使用稳定 slug。

## 验收测试

新增或修改：

```text
test_doctor_payload_uses_named_check_ids
test_doctor_payload_does_not_depend_on_index_order
test_doctor_preflight_missing_packs_warn
test_doctor_audit_missing_packs_fail
test_doctor_apply_readiness_blocker_fails_in_both_modes
```

命令：

```bash
python -m pytest tests/test_app.py tests/test_lifecycle_cli.py
```

---

## 2. 本轮推荐执行顺序

### Batch 1：最小用户体验修复

范围：

- P0-01 `init --yes` 输出 rollback；
- P0-03 partial 状态退出码。

命令：

```bash
python -m pytest tests/test_apply.py tests/test_lifecycle_cli.py
python -m pytest
python -m compileall -q src scripts
git diff --check
```

### Batch 2：状态持久化修复

范围：

- P0-02 Pack 状态持久化。

命令：

```bash
python -m pytest tests/test_apply.py tests/test_app.py tests/test_e2e_apply_bundled.py
python -m pytest
python -m compileall -q src scripts
git diff --check
```

### Batch 3：GSD/doctor 硬化

范围：

- P0-04 GSD marker 检测；
- P0-05 doctor severity。

命令：

```bash
python -m pytest tests/test_workflows.py tests/test_gsd_install_cli.py tests/test_app.py tests/test_lifecycle_cli.py
python -m pytest
python -m compileall -q src scripts
git diff --check
```

### Batch 4：文档和实施记录

范围：

- README；
- docs/how-to/install-gsd.md；
- docs/how-to/audit-and-rollback.md；
- docs/internal/IMPLEMENTATION_STATUS.md；
- changelog 如已有。

命令：

```bash
python -m pytest
python -m compileall -q src scripts
git diff --check
```

---

## 3. 完成标准

本轮完成必须满足：

1. `init --yes` human 输出包含 apply operation id。
2. `init --yes` human 输出包含 rollback 命令。
3. `.claude/ecc-init-state.json` 中 Pack 有 `status`。
4. `.claude/ecc-init-state.json` 中 Pack 有 `components_applied` 和 `components_skipped`。
5. `project_status()` 优先读取持久化 Pack 状态。
6. legacy state 仍可 fallback 推导状态。
7. `applied_with_warnings` 与 `partial` 区分清楚。
8. 非阻塞 warning 不导致 exit 4。
9. required project component preserve/skip 仍然 exit 4。
10. GSD marker 不会因 unrelated `commands/gsd-demo.md` 误判 verified。
11. `.planning/config.json` 不会单独证明 runtime installed_verified。
12. `doctor` 不再靠 hard-coded index 判断 severity。
13. `doctor --json` 输出稳定 check_id。
14. preflight 下干净项目缺 Pack/SourceLock/Receipt 是 WARN，不是 FAIL。
15. audit 下缺 Pack/SourceLock/Receipt 是 FAIL。
16. 所有新增行为有测试。
17. README / how-to 文档同步。
18. `python -m pytest` 通过。
19. `python -m compileall -q src scripts` 通过。
20. `git diff --check` 通过。

---

## 4. 给 Claude Code / DeepSeek V4 Pro 的启动提示

把本文件放到仓库根目录后，在 Claude Code 中输入：

```text
请完整阅读 CLAUDE_CODE_FIXLIST_ROUND2_0.2.0A1.md、AGENTS.md、README.md、ARCHITECTURE.md、SOURCE_POLICY.md、SECURITY.md、docs/internal/IMPLEMENTATION_STATUS.md，以及当前相关源码。

本轮只修 Alpha 收口问题，不做新功能扩张。按顺序完成：
1. init --yes human 输出 operation_id / backup_id / rollback hint；
2. Pack applied/partial/skipped 状态持久化进 .claude/ecc-init-state.json；
3. 区分 applied_with_warnings 和 partial，并修正 CLI exit code；
4. 硬化 GSD marker 检测，避免 unrelated files 误判；
5. 重构 doctor severity，禁止继续使用 hard-coded index。

不要新增 Pack，不要接入真实第三方 installer，不要复制或修改 GSD Core，不要使用并行写子 Agent。每个批次结束必须运行 targeted tests、python -m pytest、python -m compileall -q src scripts、git diff --check，并更新 docs/internal/IMPLEMENTATION_STATUS.md。
```
