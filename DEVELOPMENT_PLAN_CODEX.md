# 新一代 Claude Code 开发框架完整开发计划书

> 文档用途：将本文件放入现有 `ecc-init` 仓库根目录，交给 Codex 作为重构与开发的唯一总体计划。
> 工作仓库：`https://github.com/yuyukosama2004/ecc-init`
> 文档基准日期：2026-07-03
> 当前仓库基线：`ecc-init 0.1.0 Alpha`
> 目标版本：`0.2.0 Alpha`（架构重构版本），随后进入 `0.3.0 Beta`（能力包完善版本）
> 执行工具：Codex（本文件约束 Codex 如何在现有仓库中实施）
> 运行时目标：Claude Code + GSD Core（Codex 不是 0.2.0 产品依赖）
> 暂定项目名：继续使用 `ecc-init`，本轮不得因为改名扩大迁移范围。
> 核心决策：**直接在现有 `yuyukosama2004/ecc-init` 仓库上渐进重构；保留安装器、检测、合并、备份与回滚基础；废弃自研主开发流程；使用 GSD Core 作为唯一工作流内核。**

---

## 重要结论：本项目是否基于现有 `ecc-init`

**是。本项目必须直接基于现有 `ecc-init` 仓库继续开发。**

开发起点不是空仓库，不是新的 GSD Fork，也不是把 GSD 源码复制到另一个目录后重做。正式演进关系如下：

```text
yuyukosama2004/ecc-init 0.1.x
        │
        ├── 保留并重构
        │   ├── Python CLI
        │   ├── 技术栈检测
        │   ├── CLAUDE.md 管理区域合并
        │   ├── Skill 三方合并
        │   ├── 下载缓存
        │   ├── 备份
        │   ├── 回滚
        │   ├── 状态文件
        │   └── Windows 路径处理
        │
        ├── 逐步废弃
        │   ├── task-planning 主流程
        │   ├── verification-loop 主流程
        │   ├── 强制 dev-retrospective
        │   └── 依赖全局 CLAUDE.md 的隐式流程触发
        │
        └── 新增
            ├── GSD Workflow Adapter
            ├── Capability Pack Registry
            ├── Source Provider
            ├── InstallPlan
            ├── Transaction / Receipt / Source Lock
            ├── GSD agent_skills Bridge
            └── v1 → v2 Migration
```

### 仓库连续性硬约束

1. 所有代码修改发生在现有 `ecc-init` Git 仓库中。
2. 保留现有 Git 历史，不做“复制到新仓库后重新开始”。
3. 现有模块先通过测试保护，再逐步抽象；不得以“重构方便”为由全量删除重写。
4. `open-gsd/gsd-core` 始终是外部上游依赖。
5. 本仓库不维护 GSD 的私有分支。
6. 如 GSD 存在缺陷：
   - 先写兼容检测；
   - 必要时维护最小、显式、可删除的 patch；
   - 优先向上游提交 Issue/PR；
   - 不把修改后的 GSD 全量纳入本仓库。
7. 新架构在迁移期必须能识别旧 `ecc-init-state.json` 和旧 managed section。
8. 任何阶段都必须保证旧用户可以看到明确迁移报告，而不是突然改变行为。

---

## 0. Codex 执行契约

Codex 读取本文件后，应当遵守以下约束。Codex 是本仓库的实施工具；新框架的首要运行目标仍是 Claude Code + GSD。

### 0.1 第一轮必须先做的事情

1. 完整阅读本文件，不得只读取前半部分。
2. 阅读当前仓库：
   - `README.md`
   - `pyproject.toml`
   - `src/ecc_init/cli.py`
   - `src/ecc_init/app.py`
   - `src/ecc_init/paths.py`
   - `src/ecc_init/detect.py`
   - `src/ecc_init/merge.py`
   - `src/ecc_init/sync.py`
   - `src/ecc_init/backup.py`
   - `src/ecc_init/project.py`
   - `src/ecc_init/resources.py`
   - `src/ecc_init/util.py`
   - `src/ecc_init/resources/manifest.json`
   - `tests/` 下全部测试
3. 运行当前测试，记录基线结果：
   ```bash
   python -m pytest
   ```
4. 创建代码库结构说明，确认实际文件与本计划是否存在差异。
5. 只在实际代码确认后开始修改，不得凭本计划中的推测覆盖当前实现。
6. 第一批代码只实施“阶段 0、阶段 1”，通过全部验收后再进入后续阶段。
7. 每个阶段必须：
   - 写测试；
   - 运行相关测试；
   - 运行完整测试；
   - 检查 `git diff`；
   - 更新实施记录；
   - 不得跳过失败项并声称完成。

### 0.2 严禁事项

1. **不得 Fork、复制或直接修改 GSD Core 源码。**
2. **不得把完整 GSD 仓库复制进本仓库。**
3. **不得同时保留两套主工作流。**
   - GSD 是唯一流程权威；
   - 原 `task-planning`、`verification-loop`、三阶段 `dev-retrospective` 不再作为默认流程。
4. 不得全量安装 ECC。
5. 不得默认安装所有第三方 Skill。
6. 不得使用未固定版本的外部依赖完成正式安装。
7. 不得在安装失败后留下半安装状态。
8. 不得覆盖用户手写文件。
9. 不得删除用户修改过的旧 Skill。
10. 不得把 GitHub `main`、`next` 或 `latest` 解析结果直接作为长期状态；必须解析为具体版本或 commit 后记录。
11. 不得通过字符串拼接执行不可信 shell 命令。
12. 不得绕过许可证和来源记录。
13. 不得为了“架构整洁”一次性重写所有现有模块。
14. 不得先实现未来的上下文刷新系统；该能力必须在主架构稳定后单独实施。
15. 不得把 Superpowers 与 GSD 同时安装为主工作流。

### 0.3 变更原则

- 小步迁移，保持旧 CLI 在迁移期间可用。
- 新架构通过 Adapter、Manifest 和 Pack 逐步接管旧逻辑。
- 所有外部安装都必须可审计、可预览、可回滚。
- 所有状态文件必须带 schema version。
- 所有安装结果必须有 receipt。
- 所有用户级和项目级改动必须区分。
- 新增代码优先使用 Python 标准库；只有确有必要才新增依赖。
- 正式执行前必须支持 `--dry-run`。
- Windows 是一级支持平台，不能作为事后兼容项。

### 0.4 Codex 启动前的仓库指令文件

Codex 会自动读取仓库中的 `AGENTS.md`。本计划很长，不得把全文复制到 `AGENTS.md`；应创建一个短、稳定、可自动加载的根级 `AGENTS.md`，并让它指向本计划。

阶段 0 应创建或合并以下内容：

```markdown
# ecc-init repository instructions

## Source of truth
- Read `DEVELOPMENT_PLAN_CODEX.md` before planning or changing architecture.
- This repository evolves the existing `ecc-init`; do not create a replacement repository.
- GSD Core is an external workflow dependency. Do not fork, vendor, or directly modify GSD.

## First implementation boundary
- Follow the current phase and task boundary in the development plan.
- Do not implement later phases early.
- Inspect current code and tests before treating the plan as fact.

## Verification
- Run targeted tests after each logical change.
- Before finishing a batch, run `python -m pytest`.
- Also run `python -m compileall src`.
- Review `git diff --check` and `git diff`.

## Safety
- Do not overwrite user-authored files.
- Do not delete user-modified legacy skills.
- Do not add a production dependency without documenting the need.
- Do not execute unpinned external installers in tests.

## Subagents
- Default to the main agent for small or tightly coupled work.
- Use at most two delegated workers concurrently.
- Delegated workers must not recursively spawn agents.
- Parallel write work requires disjoint file ownership and worktrees.
- A subagent must return evidence, tests, changed files, and unresolved risks.
```

规则：

1. 如果已有用户 `AGENTS.md`，不得覆盖；在保留原文的前提下追加带标记的 managed section。
2. managed section 标记：
   ```markdown
   <!-- ecc-init-development:start -->
   ...
   <!-- ecc-init-development:end -->
   ```
3. `AGENTS.md` 只存长期稳定规则。
4. 阶段任务、临时决策、长表格留在本计划和实施记录中。
5. 不在 `AGENTS.md` 塞入外部仓库完整说明或大段 Skill 内容。
6. 子目录只有在确实需要不同测试命令或局部约束时才新增更具体的 `AGENTS.md`。

### 0.5 Codex 项目级配置建议

开发本仓库时，建议创建项目级 `.codex/config.toml`。若仓库已经存在该文件，必须合并，不得覆盖用户配置。

推荐值：

```toml
[agents]
max_threads = 3
max_depth = 1
job_max_runtime_seconds = 900
```

解释：

- `max_threads = 3`：限制同时打开的 Agent 线程；本计划进一步规定同时最多使用两个 delegated worker。
- `max_depth = 1`：根 Agent 可以创建直接子 Agent，但子 Agent 不得继续递归扩散。
- `job_max_runtime_seconds = 900`：批量 Worker 默认 15 分钟；超时后回到主 Agent 重新判断，不无限等待。

本配置是开发仓库的 Codex 约束，不是最终产品给 GSD 用户写入的配置。

### 0.6 Codex 实施记录

创建：

```text
docs/internal/IMPLEMENTATION_STATUS.md
```

最小结构：

```markdown
# Implementation Status

## Current phase
- Phase:
- Batch:
- Branch:
- Started:

## Scope
- In scope:
- Out of scope:

## Baseline
- Test command:
- Result:
- Known pre-existing failures:

## Completed
- [ ]

## Decisions
- ID:
- Decision:
- Evidence:
- Consequence:

## Subagent ledger
| ID | Role | Task | Read/Write | Files owned | Result | Retries |
|---|---|---|---|---|---|---|

## Verification
| Command | Result | Evidence |
|---|---|---|

## Remaining risks
- ...

## Next permitted batch
- ...
```

每个开发批次结束时更新。不得把“未来计划”标为已完成。

---

# 0A. Codex 开发侧子 Agent 治理

本节约束 Codex **开发 `ecc-init` 仓库本身时**的 Agent 使用。它与将来 GSD 在用户项目中的 Agent 数量是两套不同规则。

## 0A.1 目标

子 Agent 只用于：

- 隔离大量只读探索输出；
- 并行处理真正独立的问题；
- 提供独立审查；
- 分析测试、日志或外部文档；
- 降低主线程上下文污染。

子 Agent 不用于：

- 给简单修改增加仪式；
- 让多个 Agent 同时修改同一组文件；
- 代替主 Agent做架构决策；
- 无限自我审查；
- 为了“看起来是多 Agent 系统”而拆分。

## 0A.2 主 Agent 的职责

Codex 主 Agent始终负责：

1. 阅读本计划并确定当前阶段边界。
2. 确认 Git 状态和当前分支。
3. 建立基线测试。
4. 决定任务规模。
5. 锁定公共接口。
6. 分配文件所有权。
7. 选择是否使用子 Agent。
8. 整合所有修改。
9. 运行最终测试。
10. 检查 diff。
11. 更新实施记录。
12. 对完成声明负责。

子 Agent不能宣布阶段完成。

## 0A.3 任务规模评分

在启动子 Agent 前，对任务按六个维度评分，每项 0–2 分。

| 维度 | 0 分 | 1 分 | 2 分 |
|---|---|---|---|
| 文件/模块范围 | 单文件局部 | 2–4 个相关文件 | 跨层、跨模块或外部系统 |
| 需求确定性 | 输入输出明确 | 有少量待验证假设 | 需求或接口尚未确定 |
| 架构影响 | 无 | 局部接口/数据结构 | 核心架构、状态或兼容性 |
| 风险 | 文档/低风险 | 普通回归风险 | 数据、安装、供应链、删除、并发 |
| 验证难度 | 单个测试 | 多类测试 | 集成、E2E、跨平台 |
| 可拆分程度 | 不可拆且简单 | 可分探索/审查 | 多个独立交付物 |

分级：

```text
0–3：小任务
4–7：中型任务
8–12：大型任务
```

强制升级：

- 修改备份/回滚；
- 修改文件所有权；
- 删除或迁移用户文件；
- 执行外部安装器；
- 修改来源校验；
- 修改路径安全；
- 修改 JSON merge；
- 修改 GSD 安装/卸载；
- 修改供应链或许可证逻辑。

命中任一项，至少按中型任务处理；涉及不可逆数据或外部执行，按大型或高风险任务处理。

## 0A.4 各规模默认执行方式

### 小任务

```text
主 Agent阅读
→ 主 Agent修改
→ 目标测试
→ diff 检查
```

默认子 Agent数量：`0`

允许例外：

- 主上下文已经明显污染；
- 需要一个只读 Agent快速定位；
- 用户明确要求独立审查。

即便例外，也最多一个只读子 Agent。

### 中型任务

默认：

```text
主 Agent实现
→ 一个独立 Reviewer
→ 主 Agent修复
→ 最终验证
```

默认子 Agent数量：`0–1`

可选：

- 一个 read-only explorer；
- 或一个 reviewer；
- 通常不同时都启用。

### 大型任务

默认：

```text
主 Agent锁定接口和文件边界
→ 最多两个 Worker 并行
→ 主 Agent集成
→ 一个 Reviewer
→ 最终测试
```

默认并发 delegated worker：`最多 2`

单批累计新建子 Agent：`最多 4`

超过时必须：

- 停止当前批次；
- 更新实施记录；
- 说明为什么原拆分失败；
- 重新规划；
- 不得继续 fan-out。

### 高风险任务

例如事务、删除、供应链、外部 installer：

```text
一个实现者
→ 一个独立安全/正确性 Reviewer
→ 主 Agent验证
```

规则：

- 写操作默认顺序执行；
- 不允许两个 Agent并行修改风险核心；
- 必须有 failure-path 测试；
- Reviewer 不得是原实现 Agent；
- 最多两轮 review/fix。

## 0A.5 硬并发与线程约束

开发仓库默认：

```text
Codex open threads：最多 3
并发 delegated workers：最多 2
并发 write workers：默认 1
嵌套深度：1
```

并发 write workers 只有同时满足以下条件才能提升到 2：

1. 两个任务文件集合完全不重叠；
2. 公共接口已经冻结；
3. 不共同修改 manifest、state schema 或公共模型；
4. 各自在独立 Git worktree 或独立分支；
5. 有明确 merge 顺序；
6. 各自可以独立测试；
7. 主 Agent记录了 File Ownership Table。

否则必须顺序执行。

## 0A.6 阶段级调用预算

“调用”指新建一个子 Agent线程。继续同一线程不重复计数，但重试记入 retries。

| 实施阶段 | 默认上限 | 允许角色 |
|---|---:|---|
| 阶段 0–2 | 每阶段最多 2 | explorer、reviewer |
| 阶段 3–4 | 每阶段最多 4 | explorer、实现 worker、security reviewer |
| 阶段 5–8 | 每阶段最多 5 | adapter explorer、实现 worker、reviewer、E2E analyst |
| 阶段 9–11 | 每阶段最多 5 | stack worker、platform tester、release reviewer |
| 任意单批 | 最多 4 | 不得跨越批次边界累积扩散 |

超过预算不代表自动失败，但必须由用户明确授权；Codex 不得自行提高预算。

## 0A.7 重试和审查预算

- 同一个子任务最多重试 `1` 次。
- 同一个 Reviewer 最多复审 `2` 轮。
- 同一测试失败连续出现两次且没有新增证据时：
  - 停止重试；
  - 回到主 Agent；
  - 重新判断根因。
- 子 Agent超时：
  - 不立即再启动同类 Agent；
  - 先检查其已有输出、Git diff、日志。
- 不允许“实现 Agent自审通过”代替独立 Reviewer。
- 不允许 Reviewer直接扩大需求范围。

## 0A.8 允许并行的任务

优先并行：

- 不同目录的只读代码盘点；
- 文档与测试基线调查；
- 独立平台兼容性分析；
- 安全审查和测试缺口审查；
- 不同固定来源的许可证盘点；
- 不改代码的外部 API/仓库研究。

谨慎并行：

- 不同 Pack 的实现；
- 不同 Source Provider；
- 不同平台测试；
- 文档和代码。

禁止并行写：

- `src/ecc_init/app.py`
- `src/ecc_init/cli.py`
- 核心数据模型
- 状态 schema
- transaction journal
- ownership registry
- 同一个 manifest
- 同一个 config merge 函数
- 同一测试 fixture
- 同一个迁移器

除非主 Agent先拆出稳定接口，并为每个 Agent分配完全不同的文件。

## 0A.9 File Ownership Table

并行前必须写入实施记录：

```markdown
| Agent | Mode | Owned files | May read | Must not modify | Deliverable |
|---|---|---|---|---|---|
| worker-a | write | src/ecc_init/sources/github_archive.py; tests/unit/test_github_archive.py | sources/base.py | core/models.py | provider + tests |
| worker-b | write | src/ecc_init/sources/integrity.py; tests/unit/test_integrity.py | sources/base.py | core/models.py | verifier + tests |
| reviewer | read-only | none | changed files | all files | findings report |
```

子 Agent发现必须修改未分配公共文件时：

1. 不得直接修改；
2. 返回变更请求；
3. 由主 Agent决定；
4. 必要时终止并行，改为顺序执行。

## 0A.10 子 Agent输入契约

每个任务必须包含：

```text
Role:
Objective:
Why delegated:
Allowed files:
Forbidden files:
Required reads:
Public interfaces:
Acceptance criteria:
Test commands:
Return format:
Time/retry budget:
```

禁止输入：

- “看看有什么问题顺便修一下”；
- “把这一块做完”；
- 没有文件边界的“并行开发”；
- 让 Reviewer 自己决定产品范围。

## 0A.11 子 Agent输出契约

必须返回：

```markdown
## Result
- Status: completed | blocked | failed
- Summary:

## Evidence
- Files inspected:
- Symbols/paths:
- Commands run:

## Changes
- Files changed:
- Public interface changes:
- State/schema changes:

## Verification
- Tests run:
- Passed:
- Failed:
- Not run and why:

## Risks
- Remaining:
- Assumptions:
- Follow-up required:

## Integration notes
- Merge order:
- Conflicts expected:
```

只返回“已完成”视为无效结果。

## 0A.12 Reviewer 规则

Reviewer 默认 read-only，并按以下顺序：

1. 需求符合性；
2. 用户文件安全；
3. 回滚完整性；
4. 状态一致性；
5. 路径和命令注入；
6. 错误路径；
7. 测试覆盖；
8. 可维护性；
9. 文档。

Reviewer 输出 findings：

```text
BLOCKER
HIGH
MEDIUM
LOW
```

只有 BLOCKER/HIGH 阻止批次完成。MEDIUM 必须记录处理决定，LOW 可进入 backlog。

## 0A.13 第一轮开发的 Agent 限制

阶段 0、阶段 1 第一轮：

- 主 Agent承担主要实现；
- 最多使用：
  - 1 个 read-only repository explorer；
  - 1 个 read-only reviewer；
- 不允许并行写 Agent；
- 不允许任何 Agent安装 GSD；
- 不允许任何 Agent改动用户全局配置；
- 不允许跨入阶段 2。

---

# 0B. 新框架产品侧的 GSD 子 Agent 治理

本节约束未来 `ecc-init` 安装和配置 GSD 后的 Agent 使用。由于本项目不修改 GSD Runtime，必须区分“能够硬性写入 GSD 配置的约束”与“只能通过 Profile/文档建议的约束”。

## 0B.1 0.2.0 可硬性表达的配置

通过 `.planning/config.json` 的默认值建议：

```json
{
  "parallelization": {
    "enabled": true,
    "plan_level": true,
    "task_level": false,
    "skip_checkpoints": false,
    "max_concurrent_agents": 3,
    "min_plans_for_parallel": 2
  },
  "workflow": {
    "use_worktrees": true,
    "subagent_timeout": 300000,
    "node_repair_budget": 1
  }
}
```

写入规则：

- 只在键不存在时建议；
- 不覆盖用户显式值；
- 用户选择 `minimal` 时使用更保守值；
- 用户显式关闭并行时不得重新开启；
- 非 Claude Runtime 不得强制启用 Claude 专属 worktree isolation。

## 0B.2 不能伪装成硬限制的内容

如果 GSD 当前没有提供以下硬限制，本项目不得声称已经强制执行：

- 每个 Phase 累计最多调用多少 Agent；
- 每种角色最多出现几次；
- 子 Agent是否可自行再委派；
- 总 Token 预算；
- 总费用预算。

0.2.0 应：

1. 在 Profile 中记录推荐策略；
2. 在 `doctor` 中检查可检测配置；
3. 输出警告；
4. 不修改 GSD 内核实现拦截器；
5. 等待 GSD 上游提供正式扩展点后再实现硬 Gate。

## 0B.3 Product Profiles

### minimal

```json
{
  "parallelization": {
    "enabled": false,
    "plan_level": false,
    "task_level": false,
    "max_concurrent_agents": 1
  },
  "workflow": {
    "use_worktrees": false,
    "node_repair_budget": 1
  }
}
```

用途：

- 小型个人项目；
- Token 敏感；
- Windows/仓库不适合 worktree；
- 用户希望主 Agent主导。

### default

```json
{
  "parallelization": {
    "enabled": true,
    "plan_level": true,
    "task_level": false,
    "skip_checkpoints": false,
    "max_concurrent_agents": 3,
    "min_plans_for_parallel": 2
  },
  "workflow": {
    "use_worktrees": true,
    "node_repair_budget": 1
  }
}
```

语义：

- 只在 Plan 层并行；
- 不把每个小 Task 单独 fan-out；
- 保留检查点；
- 并发最多 3；
- 失败修复不无限循环。

### frontend

沿用 default，增加软预算：

```text
UI researcher：1
UI checker：1
执行 Agent：按独立计划最多 3 并发
UI auditor/reviewer：1
单 Phase 推荐累计 Agent调用：不超过 8
```

这是推荐预算，不在 0.2.0 声称硬拦截。

### high-assurance

```json
{
  "parallelization": {
    "enabled": true,
    "plan_level": true,
    "task_level": false,
    "skip_checkpoints": false,
    "max_concurrent_agents": 2,
    "min_plans_for_parallel": 2
  },
  "workflow": {
    "use_worktrees": true,
    "node_repair_budget": 1,
    "code_review": true,
    "verifier": true,
    "security_enforcement": true
  }
}
```

用途：

- 安全；
- 迁移；
- 支付；
- 权限；
- 供应链；
- 数据删除。

## 0B.4 GSD 并行允许条件

Profile 文档必须写明：

- 任务存在独立 Plan；
- 接口已冻结；
- 文件所有权不重叠；
- Worktree 可用；
- 每个 Plan 有独立测试；
- 没有共享迁移冲突；
- 没有未解决设计决策。

不满足时建议顺序执行。

## 0B.5 Pack 不得自行扩张 Agent 数量

Capability Pack 只能：

- 提供 Skill；
- 把 Skill绑定到已有 GSD Agent；
- 提供配置建议。

Pack 不得：

- 新建一套主编排；
- 自动要求每个 Skill启动一个 Agent；
- 因安装多个 Pack线性增加 Reviewer 数量；
- 给所有 GSD Agent都注入全部 Skill；
- 在 Skill 中写“必须再启动多个 Agent”。

## 0B.6 观测与报告

状态输出应显示：

```text
GSD concurrency configured: 3
Plan-level parallelization: enabled
Task-level parallelization: disabled
Worktrees: enabled
Repair budget: 1
Agent policy source: profile:default
User overrides detected: ...
Hard-enforced fields: ...
Advisory-only fields: ...
```

不得把 advisory-only 写成 enforced。


---

# 1. 项目定义

## 1.1 新框架是什么

新框架是一个面向 Claude Code 的模块化开发环境组装器，由以下部分组成：

1. **GSD Core 工作流内核**
   - 管理需求讨论、规划、执行、验证、UI 阶段、代码审查和交付。
2. **框架管理器**
   - 由现有 `ecc-init` 演化而来；
   - 负责安装、配置、更新、卸载、状态、备份和回滚。
3. **能力包系统**
   - 根据技术栈和用户选择安装专业 Skill。
4. **开源来源管理系统**
   - 从固定版本的 GitHub、npm 或本地来源获取组件。
5. **GSD 配置桥接层**
   - 把已安装 Skill 注入指定 GSD Agent。
6. **技术栈检测系统**
   - 识别 Python、FastAPI、React、TypeScript、LangChain、LangGraph、Java、Spring Boot 等。
7. **质量与安全层**
   - 复用 GSD 原生验证、代码审查和安全门；
   - 可叠加专业审查 Skill。
8. **前端设计与视觉验证层**
   - 使用 GSD UI Phase、UI Review；
   - 叠加 UI/UX、React 和 Web 设计能力。
9. **安装状态与证据层**
   - 记录来源、版本、文件、哈希、配置注入、备份和冲突。
10. **未来上下文增强层**
    - 结构化 Checkpoint、独立审核和上下文恢复；
    - 不属于 0.2.0 MVP。

## 1.2 新框架不是什么

它不是：

- GSD 的 Fork；
- ECC 的精简复制品；
- 一组无组织的 `SKILL.md`；
- 自己重新实现的多 Agent Harness；
- 通用 IDE；
- 独立编程模型；
- 自动生成所有代码的黑盒系统；
- 默认全局污染用户 Claude Code 配置的“大礼包”。

## 1.3 核心职责边界

```text
GSD Core
  负责：流程、阶段、子 Agent、计划、执行、验证、交付

ecc-init 管理器
  负责：安装、组合、来源、版本、配置、更新、卸载、回滚

Capability Pack
  负责：提供某一领域“具体怎么做”的知识和工具

GSD Bridge
  负责：把 Pack 中的 Skill 绑定到适当的 GSD Agent

External Tool
  负责：浏览器、测试、Git、MCP 等真实操作

State/Receipt
  负责：记录安装事实，而不是记录聊天推理
```

任何模块不得跨越边界重新实现另一模块的职责。

---

# 2. 总体架构

## 2.1 逻辑架构

```text
┌──────────────────────────────────────────────────────────────┐
│                         CLI / UX Layer                       │
│ init / plan / apply / status / update / doctor / remove      │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                     Application Service Layer                │
│ 初始化编排、迁移、安装计划、事务、报告、错误映射             │
└───────────────┬───────────────────────┬──────────────────────┘
                │                       │
┌───────────────▼─────────────┐ ┌──────▼───────────────────────┐
│ Workflow Adapter Layer      │ │ Capability Pack Layer        │
│ GSD adapter                 │ │ pack resolver                │
│ future: superpowers adapter │ │ dependency/conflict resolver │
└───────────────┬─────────────┘ └──────┬───────────────────────┘
                │                       │
┌───────────────▼───────────────────────▼───────────────────────┐
│                    Source Acquisition Layer                  │
│ GitHub directory / archive / npm / external CLI / local      │
│ version pin / cache / hash / license / staging               │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                 Transaction & File Ownership Layer           │
│ backup / atomic writes / merge / rollback / receipts         │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                    Runtime Integration Layer                 │
│ Claude Home / project skills / GSD config / pending config   │
└──────────────────────────────┬───────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────┐
│                       State & Audit Layer                    │
│ global state / project state / source lock / install receipt │
└──────────────────────────────────────────────────────────────┘
```

## 2.2 运行时架构

用户执行：

```bash
ecc-init init . --workflow gsd --profile default
```

系统执行：

```text
识别项目
→ 读取用户配置和现有状态
→ 解析 Workflow、Profile、Pack
→ 解析外部来源为固定版本
→ 生成 InstallPlan
→ 展示预览
→ 运行环境检查
→ 创建备份
→ 安装或确认 GSD
→ 获取并安装能力包
→ 写入或排队 GSD agent_skills 配置
→ 验证文件、命令和状态
→ 写入 Receipt
→ 完成事务
```

---

# 3. 开源仓库来源清单

本节是正式的来源策略，不得随意替换仓库。

## 3.1 GSD Core

- 仓库：`https://github.com/open-gsd/gsd-core`
- npm 包：`@opengsd/gsd-core`
- 当前计划基准版本：`1.6.0`
- 当前包要求：以其 `package.json` 为准；本计划基准要求 Node.js `>=22`、npm `>=10`
- 许可证：MIT
- 作用：
  - 唯一工作流内核；
  - 提供 Discuss、Plan、Execute、Verify、Ship；
  - 提供 UI Phase、UI Review；
  - 提供代码审查、安全门、Worktree、子 Agent、状态文件；
  - 提供 `agent_skills` 注入。
- 获取方式：
  - **不复制源码；**
  - 通过固定版本 npm 命令安装；
  - 默认 Claude Code 全局安装；
  - 安装命令由 `GsdWorkflowAdapter` 生成。
- 基准命令：
  ```bash
  npx --yes @opengsd/gsd-core@1.6.0 --claude --global
  ```
- 禁止：
  - 使用 `@latest` 作为已记录版本；
  - 直接复制 `agents/`、`commands/`；
  - 修改 GSD 安装后的内部文件来实现本项目功能。
- 配置接入：
  - `.planning/config.json`
  - `agent_skills`
  - `workflow.*`
  - `response_language`
  - `claude_md_path`
- 更新策略：
  - `ecc-init update --workflow` 才解析新版本；
  - 必须先显示变更；
  - 必须记录旧版本、新版本和安装输出；
  - 失败必须回滚本项目管理的改动，并明确说明 GSD 外部安装状态。

## 3.2 Everything Claude Code（ECC）

- 仓库：`https://github.com/affaan-m/ECC`
- 许可证：MIT（仍需为每个同步文件保存来源）
- 作用：
  - 只作为部分语言、框架、安全 Skill 的来源；
  - 不作为工作流；
  - 不安装完整 ECC。
- 初始允许获取的目录：
  - `skills/python-patterns/`
  - `skills/fastapi-patterns/`
  - `skills/react-patterns/`
  - `skills/java-coding-standards/`
  - `skills/springboot-patterns/`
  - 经审核后可加入明确指定的安全 Skill
- 获取方式：
  - 固定 Git tag、release 或 commit；
  - 只提取 Manifest 指定目录；
  - 保存 LICENSE、源路径、commit、SHA256。
- 禁止：
  - 自动发现并安装 ECC 全部 Skill；
  - 同步 ECC 的主流程 Skill；
  - 同步 ECC hooks、commands、agents 作为默认组件；
  - 用 ECC 的规划规则覆盖 GSD。

## 3.3 UI UX Pro Max

- 仓库：`https://github.com/nextlevelbuilder/ui-ux-pro-max-skill`
- 基准版本：`v2.5.0`，实施时必须重新确认 npm/GitHub 对应关系
- 许可证：MIT
- 作用：
  - 提供设计系统生成；
  - 色彩、字体、风格、产品类型、UX 指南；
  - 生成 `design-system/MASTER.md` 和页面覆盖文件。
- 默认归属：
  - `frontend-design` Pack 的可选/推荐组件。
- 获取方式优先级：
  1. 使用其官方 CLI 在临时 staging 目录生成 Claude Code Skill；
  2. 验证输出；
  3. 通过本项目事务层复制到目标；
  4. 记录来源和生成命令。
- 参考命令，实施前必须验证：
  ```bash
  npx --yes uipro-cli@<PINNED_VERSION> init --ai claude --offline
  ```
- 如果固定版本 CLI 不支持 staging：
  - 使用固定 tag 的源码包；
  - 只复制官方指定 source-of-truth 目录；
  - 不手工删减数据文件。
- 不得默认全局安装。
- 不得把它当作主工作流。

## 3.4 Vercel Agent Skills

- 仓库：`https://github.com/vercel-labs/agent-skills`
- 许可证：MIT
- 初始获取：
  - `skills/react-best-practices/`
  - `skills/web-design-guidelines/`
  - 未来可选 `composition-patterns/`
- 作用：
  - React/Next.js 性能和结构规范；
  - Web 设计、可访问性、交互和 UX 审查。
- 获取方式：
  - 固定 commit 或 tag；
  - 使用 `github_directory` Source Provider；
  - 保留 `SKILL.md`、`rules/`、`references/`、必要脚本。
- 特殊处理：
  - 不应无条件把巨大的编译型 `AGENTS.md` 注入每个上下文；
  - 第一版保持来源目录完整，但 GSD 注入只指向 `SKILL.md`；
  - 后续若排除重复文件，必须在 Manifest 中明确 `projection`，并添加完整性测试。
- Agent 绑定：
  - `react-best-practices`：
    - `gsd-executor`
    - `gsd-code-reviewer`
    - 必要时 `gsd-planner`
  - `web-design-guidelines`：
    - `gsd-ui-checker`
    - `gsd-ui-auditor`
    - `gsd-code-reviewer`

## 3.5 Anthropic Skills

- 仓库：`https://github.com/anthropics/skills`
- 候选目录：
  - `skills/frontend-design/`
  - `skills/webapp-testing/`
- 许可证：
  - 各 Skill 可能使用自定义 `LICENSE.txt`；
  - 不得假定为 MIT；
  - 不得在本包内重新分发，除非许可证审计明确允许。
- 作用：
  - `frontend-design`：增强创意设计方向；
  - `webapp-testing`：Playwright 本地 Web 应用测试辅助。
- 获取方式：
  - 默认作为“外部可选组件”；
  - 用户明确选择后，从上游安装或引用；
  - 保存许可证接受记录；
  - 不将源码打包进 `ecc-init` wheel。
- 第一版默认：
  - `frontend-design` 为 optional；
  - `webapp-testing` 为 optional；
  - 缺少它们不得阻塞基础前端 Pack。

## 3.6 Open GSD Browser

- 仓库：`https://github.com/open-gsd/gsd-browser`
- 许可证：实施时核验，当前预期为 Apache-2.0
- 作用：
  - 浏览器操作；
  - 截图；
  - 可访问性检查；
  - visual diff；
  - 辅助 GSD UI Review。
- 第一版定位：
  - optional tool integration；
  - 不作为 `0.2.0` 发布阻塞项。
- 集成前提：
  - 有稳定发布和明确安装命令；
  - 有卸载方式；
  - 可检测是否已配置为 MCP 或 CLI；
  - 不执行来源不明的二进制。

## 3.7 Superpowers

- 仓库：`https://github.com/obra/superpowers`
- 作用：
  - 仅作为方法论和测试设计参考；
  - 可参考其精确计划、TDD、独立 Reviewer 思路。
- 默认行为：
  - 不安装；
  - 不复制其主工作流；
  - 不与 GSD 同时作为 Workflow。
- 未来：
  - 可以开发独立 `SuperpowersWorkflowAdapter`；
  - 与 GSD 互斥；
  - 不属于 0.2.0。

## 3.8 Vercel Skills CLI

- 仓库：`https://github.com/vercel-labs/skills`
- 作用：
  - 可作为第三方 Agent Skill 安装协议参考；
  - 第一版不应依赖它完成核心安装。
- 原因：
  - 本框架需要统一 receipt、事务、来源锁定和回滚；
  - 直接调用通用 CLI 可能绕过本框架状态管理。
- 可用于：
  - 用户手动安装；
  - 后续 ExternalInstaller Provider。

---

# 4. 默认框架组成

## 4.1 默认 Profile：`default`

```text
workflow:
  gsd

packs:
  project-baseline
  stack-auto
  quality-basic

conditional:
  frontend detected:
    frontend-essential
  fastapi detected:
    python-fastapi
  langchain/langgraph detected:
    rag-python
  java/spring detected:
    java-spring
```

## 4.2 Profile：`minimal`

```text
workflow:
  gsd

packs:
  project-baseline

不安装:
  UI 设计库
  外部测试 Skill
  深度安全 Pack
```

## 4.3 Profile：`frontend`

```text
workflow:
  gsd

packs:
  project-baseline
  frontend-essential
  quality-basic
```

## 4.4 Profile：`rag`

```text
workflow:
  gsd

packs:
  project-baseline
  python-fastapi
  rag-python
  quality-basic
```

## 4.5 Profile：`none`

```text
workflow:
  none

用途:
  只安装能力包，不安装 GSD
```

`none` 主要用于高级用户和测试，不是默认推荐。

---

# 5. 能力包设计

## 5.1 Pack 的定义

Pack 是一个声明式组件集合，包含：

- ID；
- 版本；
- 描述；
- 触发条件；
- 依赖；
- 冲突；
- 来源组件；
- 安装目标；
- GSD Agent 绑定；
- 配置建议；
- 验证规则；
- 许可证要求；
- 可执行表面声明。

Pack 不得包含主流程指令。

## 5.2 `project-baseline`

组成：

- 项目技术栈摘要；
- 项目级 Skill 根目录；
- GSD pending config 机制；
- 安装状态；
- 来源锁文件；
- 不再默认生成强制开发复盘流程。

保留现有文件的策略：

- `docs/PROJECT_OVERVIEW.md`：
  - 保留；
  - 只在不存在时创建；
  - 后续由 GSD codebase map 替代其主作用。
- `docs/DEVELOPMENT_LOG.md`：
  - 保留用户文件；
  - 不再强制更新。
- `docs/dev-notes/`：
  - 保留；
  - 不纳入默认流程。

## 5.3 `quality-basic`

默认优先使用 GSD 原生：

- `workflow.plan_check = true`
- `workflow.verifier = true`
- `workflow.code_review = true`
- `workflow.security_enforcement = true`

可叠加现有 Skill：

- `code-review`：
  - 重命名或迁移为 `ecc-code-review`，避免与其他来源同名；
  - 作为可选辅助，不替代 GSD Reviewer。
- `security-review`：
  - 迁移为 `ecc-security-review`；
  - 绑定 `gsd-code-reviewer`、`gsd-verifier`；
  - 不绑定所有 Agent。
- `code-tour`：
  - 默认不再通过全局 CLAUDE.md 强制触发；
  - 可改为显式 Skill；
  - GSD 项目优先使用 `/gsd-map-codebase`。

## 5.4 `frontend-essential`

### 必需组件

1. GSD 原生 UI Phase
2. GSD 原生 UI Review
3. Vercel `web-design-guidelines`
4. React 项目条件安装 Vercel `react-best-practices`

### 推荐组件

5. UI UX Pro Max

### 可选组件

6. Anthropic `frontend-design`
7. Anthropic `webapp-testing`
8. GSD Browser

### GSD 绑定建议

```json
{
  "agent_skills": {
    "gsd-ui-researcher": [
      ".claude/skills/ui-ux-pro-max"
    ],
    "gsd-ui-checker": [
      ".claude/skills/web-design-guidelines"
    ],
    "gsd-ui-auditor": [
      ".claude/skills/web-design-guidelines"
    ],
    "gsd-executor": [
      ".claude/skills/vercel-react-best-practices"
    ],
    "gsd-code-reviewer": [
      ".claude/skills/vercel-react-best-practices",
      ".claude/skills/web-design-guidelines"
    ]
  }
}
```

如果安装了 Anthropic `frontend-design`：

```json
{
  "agent_skills": {
    "gsd-ui-researcher": [
      ".claude/skills/ui-ux-pro-max",
      ".claude/skills/frontend-design"
    ]
  }
}
```

### GSD 配置建议

仅在键不存在时建议：

```json
{
  "workflow": {
    "ui_phase": true,
    "ui_safety_gate": true,
    "ui_review": true
  }
}
```

不得覆盖用户显式设置的 `false`。

## 5.5 `python-fastapi`

来源：

- ECC `python-patterns`
- ECC `fastapi-patterns`
- 当前自定义模板作为离线 fallback

绑定：

```json
{
  "agent_skills": {
    "gsd-planner": [
      ".claude/skills/python-patterns",
      ".claude/skills/fastapi-patterns"
    ],
    "gsd-executor": [
      ".claude/skills/python-patterns",
      ".claude/skills/fastapi-patterns"
    ],
    "gsd-code-reviewer": [
      ".claude/skills/python-patterns",
      ".claude/skills/fastapi-patterns"
    ]
  }
}
```

只有检测到 FastAPI 才加入 `fastapi-patterns`。

## 5.6 `rag-python`

组成：

- `langchain-patterns`
- `langgraph-patterns`
- 未来可增加 `rag-patterns`
- 不应自动增加向量数据库、模型供应商等无关依赖

绑定：

- `gsd-phase-researcher`
- `gsd-planner`
- `gsd-executor`
- `gsd-code-reviewer`

原则：

- Skill 只提供领域模式；
- 不改变 GSD 的计划格式；
- 不在 Skill 中重复要求“先计划后实现”。

## 5.7 `java-spring`

组成：

- ECC `java-coding-standards`
- ECC `springboot-patterns`

绑定：

- `gsd-planner`
- `gsd-executor`
- `gsd-code-reviewer`

Spring Boot 未检测到时，只安装 Java Skill。

## 5.8 `security-deep`

组成：

- `ecc-security-review`
- 未来可接入 AgentShield，但必须单独做 executable surface 审计

绑定：

- `gsd-code-reviewer`
- `gsd-verifier`

默认不安装的原因：

- GSD 已有基础安全 enforcement；
- 深度安全检查增加成本；
- 某些项目不需要每阶段执行。

## 5.9 `context-refresh-experimental`

不在 0.2.0 实施。

未来组成：

```text
/context-checkpoint
→ 结构化状态提取
→ 独立 Reviewer 审核
→ 保存 source refs
→ 用户 clear/new session
→ 恢复一致性检查
```

必须建立在稳定的 State、Receipt、GSD Artifact 体系之上。

---

# 6. 目标代码目录

保持 Python 包名 `ecc_init`，逐步把当前大函数拆分。

```text
ecc-init/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── pyproject.toml
├── DEVELOPMENT_PLAN_CODEX.md
├── AGENTS.md
├── .codex/
│   ├── config.toml
│   └── agents/
│       ├── repo-explorer.toml
│       └── reviewer.toml
├── src/
│   └── ecc_init/
│       ├── __init__.py
│       ├── cli.py
│       ├── app.py
│       ├── errors.py
│       ├── logging.py
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── plan.py
│       │   ├── transaction.py
│       │   ├── ownership.py
│       │   ├── state_store.py
│       │   ├── receipt.py
│       │   └── validation.py
│       │
│       ├── workflows/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── none.py
│       │   └── gsd.py
│       │
│       ├── packs/
│       │   ├── __init__.py
│       │   ├── models.py
│       │   ├── registry.py
│       │   ├── resolver.py
│       │   ├── installer.py
│       │   └── gsd_bridge.py
│       │
│       ├── sources/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── registry.py
│       │   ├── github_archive.py
│       │   ├── github_directory.py
│       │   ├── npm.py
│       │   ├── external_cli.py
│       │   ├── bundled.py
│       │   ├── cache.py
│       │   ├── integrity.py
│       │   └── licenses.py
│       │
│       ├── migration/
│       │   ├── __init__.py
│       │   ├── legacy_v1.py
│       │   └── reports.py
│       │
│       ├── detect.py
│       ├── paths.py
│       ├── merge.py
│       ├── backup.py
│       ├── resources.py
│       ├── util.py
│       │
│       └── resources/
│           ├── registry/
│           │   ├── sources.json
│           │   ├── workflows.json
│           │   ├── packs/
│           │   │   ├── project-baseline.json
│           │   │   ├── quality-basic.json
│           │   │   ├── frontend-essential.json
│           │   │   ├── python-fastapi.json
│           │   │   ├── rag-python.json
│           │   │   ├── java-spring.json
│           │   │   └── security-deep.json
│           │   └── profiles/
│           │       ├── default.json
│           │       ├── minimal.json
│           │       ├── frontend.json
│           │       └── rag.json
│           │
│           ├── bundled_skills/
│           │   ├── langchain-patterns/
│           │   ├── langgraph-patterns/
│           │   └── ...
│           │
│           ├── overlays/
│           │   ├── gsd/
│           │   └── packs/
│           │
│           └── templates/
│
└── tests/
    ├── unit/
    │   ├── test_models.py
    │   ├── test_plan.py
    │   ├── test_state_store.py
    │   ├── test_receipt.py
    │   ├── test_pack_resolver.py
    │   ├── test_gsd_bridge.py
    │   ├── test_source_registry.py
    │   ├── test_github_archive.py
    │   ├── test_integrity.py
    │   ├── test_migration_v1.py
    │   └── ...
    ├── integration/
    │   ├── test_init_gsd_fake_runner.py
    │   ├── test_install_frontend_pack.py
    │   ├── test_update_pack.py
    │   ├── test_remove_pack.py
    │   ├── test_full_rollback.py
    │   └── test_windows_paths.py
    ├── e2e/
    │   ├── test_real_gsd_install.py
    │   └── test_real_sources.py
    └── fixtures/
        ├── projects/
        ├── archives/
        ├── manifests/
        └── homes/
```

说明：

- 现有文件先保留；
- 不要求第一阶段立即创建全部文件；
- 按实施阶段逐步引入；
- `app.py` 最终只保留应用服务入口，不继续堆积安装细节。

---

# 7. 核心数据模型

建议使用 `dataclasses` 和 `Enum`，第一版不强制引入 Pydantic。

## 7.1 SourceSpec

```python
@dataclass(frozen=True)
class SourceSpec:
    source_id: str
    kind: str
    repository: str | None
    package: str | None
    version: str
    commit: str | None
    path: str | None
    license_id: str | None
    license_path: str | None
    integrity: str | None
    executable_surface: tuple[str, ...]
```

## 7.2 ComponentSpec

```python
@dataclass(frozen=True)
class ComponentSpec:
    component_id: str
    source_id: str
    install_name: str
    target_scope: str
    target_subdir: str
    projection_include: tuple[str, ...]
    projection_exclude: tuple[str, ...]
    required: bool
```

## 7.3 PackSpec

```python
@dataclass(frozen=True)
class PackSpec:
    pack_id: str
    version: int
    description: str
    components: tuple[str, ...]
    requires: tuple[str, ...]
    conflicts: tuple[str, ...]
    stack_conditions: tuple[str, ...]
    gsd_agent_skills: dict[str, tuple[str, ...]]
    gsd_config_defaults: dict
```

## 7.4 WorkflowSpec

```python
@dataclass(frozen=True)
class WorkflowSpec:
    workflow_id: str
    adapter: str
    source_id: str | None
    scope_default: str
    conflicts: tuple[str, ...]
```

## 7.5 InstallPlan

```python
@dataclass
class InstallPlan:
    project_root: Path
    workflow: str
    workflow_scope: str
    packs: list[str]
    resolved_components: list[ResolvedComponent]
    state_migrations: list[StateMigration]
    file_operations: list[FileOperation]
    external_operations: list[ExternalOperation]
    config_operations: list[ConfigOperation]
    warnings: list[str]
```

InstallPlan 必须：

- 可序列化为 JSON；
- 支持 `--dry-run`；
- 不包含 secret；
- 记录所有目标路径；
- 区分 external operation 和 file operation。

## 7.6 InstallReceipt

```json
{
  "schema_version": 2,
  "operation_id": "20260629T120000Z-xxxx",
  "created_at": "2026-06-29T12:00:00Z",
  "project_root": "D:/Projects/demo",
  "workflow": {
    "id": "gsd",
    "version": "1.6.0",
    "scope": "global",
    "status": "installed"
  },
  "packs": [
    {
      "id": "frontend-essential",
      "version": 1
    }
  ],
  "sources": [
    {
      "id": "vercel-agent-skills",
      "resolved_ref": "commit-sha",
      "integrity": "sha256:..."
    }
  ],
  "files": [
    {
      "path": ".claude/skills/web-design-guidelines/SKILL.md",
      "owner": "pack:frontend-essential",
      "sha256": "...",
      "previous_sha256": null
    }
  ],
  "config_changes": [],
  "backup_id": "...",
  "result": "success"
}
```

## 7.7 Project State v2

目标路径：

```text
项目/.claude/ecc-init-state.json
```

结构：

```json
{
  "schema_version": 2,
  "tool_version": "0.2.0",
  "project_root": "...",
  "detected_stacks": [],
  "detection_evidence": {},
  "workflow": {
    "id": "gsd",
    "scope": "global",
    "requested_version": "1.6.0",
    "resolved_version": "1.6.0",
    "installed": true
  },
  "profiles": ["default"],
  "agent_policy": {
    "profile": "default",
    "max_concurrent_agents": 3,
    "plan_level_parallel": true,
    "task_level_parallel": false,
    "advisory_phase_budget": 8
  },
  "packs": {},
  "managed_files": {},
  "source_locks": {},
  "pending_gsd_config": {},
  "last_operation_id": "...",
  "last_initialized_at": "..."
}
```

## 7.8 Global State v2

目标路径：

```text
~/.ecc-init/state.json
```

记录：

- 已确认的全局 Workflow；
- GSD 版本；
- 全局 Skill；
- 全局文件所有权；
- 缓存索引；
- 最近操作；
- 工具版本；
- 不记录项目内部业务状态。

## 7.9 Source Lock

目标路径：

```text
项目/.claude/ecc-sources.lock.json
```

内容：

- source ID；
- 请求版本；
- 实际 tag；
- commit；
- archive hash；
- 选取路径；
- 许可证；
- 安装时间。

用户只有运行显式 update 才改变 lock。

---

# 8. Manifest 设计

## 8.1 `sources.json`

示例：

```json
{
  "schema_version": 1,
  "sources": {
    "gsd-core": {
      "kind": "npm-workflow",
      "package": "@opengsd/gsd-core",
      "version": "1.6.0",
      "repository": "https://github.com/open-gsd/gsd-core",
      "license": "MIT",
      "executable_surface": [
        "installer",
        "hooks",
        "commands",
        "agents"
      ]
    },
    "ecc": {
      "kind": "github-archive",
      "repository": "affaan-m/ECC",
      "version": "<PINNED_RELEASE>",
      "license": "MIT"
    },
    "vercel-agent-skills": {
      "kind": "github-archive",
      "repository": "vercel-labs/agent-skills",
      "commit": "<PINNED_COMMIT>",
      "license": "MIT"
    },
    "ui-ux-pro-max": {
      "kind": "external-cli",
      "repository": "nextlevelbuilder/ui-ux-pro-max-skill",
      "package": "uipro-cli",
      "version": "<PINNED_VERSION>",
      "license": "MIT"
    }
  }
}
```

`<PINNED_...>` 在实施阶段必须替换为实际固定值，不能发布占位符。

## 8.2 Pack Manifest

示例：

```json
{
  "schema_version": 1,
  "id": "frontend-essential",
  "description": "GSD UI flow plus UI/UX and React implementation guidance.",
  "requires": ["project-baseline"],
  "conflicts": [],
  "components": [
    {
      "id": "ui-ux-pro-max",
      "source": "ui-ux-pro-max",
      "install_name": "ui-ux-pro-max",
      "scope": "project",
      "required": false
    },
    {
      "id": "web-design-guidelines",
      "source": "vercel-agent-skills",
      "source_path": "skills/web-design-guidelines",
      "install_name": "web-design-guidelines",
      "scope": "project",
      "required": true
    },
    {
      "id": "react-best-practices",
      "source": "vercel-agent-skills",
      "source_path": "skills/react-best-practices",
      "install_name": "vercel-react-best-practices",
      "scope": "project",
      "when_stack": ["react", "nextjs"],
      "required": false
    }
  ],
  "gsd": {
    "config_defaults": {
      "workflow.ui_phase": true,
      "workflow.ui_review": true,
      "workflow.ui_safety_gate": true
    },
    "agent_skills": {
      "gsd-ui-researcher": [".claude/skills/ui-ux-pro-max"],
      "gsd-ui-checker": [".claude/skills/web-design-guidelines"],
      "gsd-ui-auditor": [".claude/skills/web-design-guidelines"],
      "gsd-executor": [".claude/skills/vercel-react-best-practices"],
      "gsd-code-reviewer": [
        ".claude/skills/vercel-react-best-practices",
        ".claude/skills/web-design-guidelines"
      ]
    }
  }
}
```

## 8.3 Profile Manifest

```json
{
  "schema_version": 1,
  "id": "default",
  "workflow": "gsd",
  "packs": [
    "project-baseline",
    "quality-basic",
    "stack-auto"
  ],
  "conditional_packs": {
    "frontend": "frontend-essential",
    "fastapi": "python-fastapi",
    "langchain": "rag-python",
    "langgraph": "rag-python",
    "spring-boot": "java-spring"
  }
}
```

---

# 9. Workflow Adapter

## 9.1 接口

```python
class WorkflowAdapter(Protocol):
    workflow_id: str

    def inspect(self, context: WorkflowContext) -> WorkflowStatus:
        ...

    def plan_install(self, context: WorkflowContext) -> list[Operation]:
        ...

    def apply_install(self, context: WorkflowContext, runner: CommandRunner) -> WorkflowResult:
        ...

    def plan_update(self, context: WorkflowContext) -> list[Operation]:
        ...

    def apply_update(self, context: WorkflowContext, runner: CommandRunner) -> WorkflowResult:
        ...

    def plan_remove(self, context: WorkflowContext) -> list[Operation]:
        ...

    def verify(self, context: WorkflowContext) -> list[CheckResult]:
        ...
```

## 9.2 GSD Adapter

文件：

```text
src/ecc_init/workflows/gsd.py
```

职责：

1. 检测 Node 和 npm。
2. 检查版本：
   ```bash
   node --version
   npm --version
   ```
3. 以 `subprocess.run([...], shell=False)` 执行。
4. 使用固定版本。
5. 传递环境：
   - `CLAUDE_CONFIG_DIR`
   - 继承必要 PATH
6. 捕获：
   - stdout；
   - stderr；
   - return code；
   - 启动时间；
   - 结束时间。
7. 在执行前：
   - 快照 Claude 配置目录；
   - 创建备份。
8. 在执行后：
   - 识别新增/修改文件；
   - 写 receipt；
   - 验证 GSD 命令/Skill 文件；
   - 不解析用户私密内容。
9. 安装已存在同版本：
   - 视为 idempotent；
   - 允许官方 installer 自检；
   - 不重复写 Pack。
10. 更新：
    - 显式命令；
    - 先展示目标版本；
    - 重新运行固定版本 installer；
    - 保存前后差异。
11. 卸载：
    - 优先调用 GSD 官方卸载方式；
    - 如果官方方式不可用，不得盲删；
    - 只删除 receipt 证明由本工具安装且哈希未变化的文件；
    - 用户修改过的文件必须保留并报告。

## 9.3 `none` Adapter

用于只装 Skill 的用户和测试：

- 不执行外部命令；
- `verify` 永远返回可用；
- GSD 配置操作写入 pending，不直接报错。

## 9.4 未来 Superpowers Adapter

仅保留接口扩展能力，不在本轮实现。

---

# 10. GSD 配置桥

## 10.1 核心原则

- 不修改 GSD 安装文件；
- 只修改项目 `.planning/config.json`；
- 如果文件尚不存在，写入 pending；
- 不覆盖用户值；
- 数组使用去重合并；
- 卸载 Pack 时只移除本 Pack 加入且仍未被其他 Pack 使用的值。

## 10.2 Pending 配置

路径：

```text
项目/.claude/ecc-pending-gsd.json
```

当 `.planning/config.json` 不存在：

```json
{
  "schema_version": 1,
  "agent_skills": {},
  "config_defaults": {},
  "created_at": "...",
  "packs": []
}
```

提供命令：

```bash
ecc-init sync-gsd .
```

行为：

- 检测 `.planning/config.json`；
- 合并 pending；
- 写 receipt；
- 清理已应用 pending；
- 不需要用户重新安装 Pack。

## 10.3 三方合并

GSD JSON 配置不能简单覆盖。

为每个本项目管理的 JSON path 记录：

```json
{
  "path": "agent_skills.gsd-executor",
  "base": [],
  "last_applied": [".claude/skills/python-patterns"],
  "owner": "pack:python-fastapi"
}
```

更新时：

- 用户未修改：直接升级；
- 用户追加值：保留用户值并追加新值；
- 用户删除本工具值：
  - 视为用户显式选择；
  - 不自动重新加入，除非用户 `--force-managed-config`；
- 多 Pack 共享值：
  - 使用引用计数或 owners 集合；
  - 卸载一个 Pack 不删除另一个仍需要的值。

## 10.4 默认配置策略

Pack 的 `config_defaults` 只在以下情况下写入：

- 键不存在；
- 键为 null；
- 用户明确运行 `--apply-recommended-config`。

不得覆盖：

- 用户显式 false；
- 用户模型选择；
- 用户并发数；
- 用户 Git 策略；
- 用户安全等级。

---

# 11. Source Provider 系统

## 11.1 Provider 接口

```python
class SourceProvider(Protocol):
    kind: str

    def resolve(self, spec: SourceSpec, offline: bool) -> ResolvedSource:
        ...

    def fetch(self, resolved: ResolvedSource, cache: CacheStore) -> FetchedSource:
        ...

    def stage(self, fetched: FetchedSource, staging_dir: Path) -> StagedSource:
        ...

    def verify(self, staged: StagedSource) -> list[CheckResult]:
        ...
```

## 11.2 GitHub Archive Provider

功能：

- 下载固定 tag/commit archive；
- 防 Zip Slip；
- 限制解压路径；
- 限制文件数量和总大小；
- 计算 SHA256；
- 缓存；
- 提取指定子目录；
- 保存 LICENSE；
- 不执行 archive 内脚本。

安全检查：

- 路径不得包含 `..`；
- 绝对路径拒绝；
- symlink 默认拒绝；
- 超限拒绝；
- 目标目录必须在 staging 内；
- 下载 URL host 必须在 allowlist。

## 11.3 GitHub Directory Provider

第一版可以基于 archive 实现：

```text
下载一次固定 commit archive
→ 提取指定目录
```

不要逐文件网络请求，避免不一致和限流。

## 11.4 npm Workflow Provider

只用于 GSD 等明确外部程序。

要求：

- package 名在 allowlist；
- version 是固定 semver；
- 不接受用户输入拼接；
- `shell=False`；
- `--yes`；
- 记录 package/version；
- 记录 executable surface；
- 记录命令输出；
- 默认禁止 prerelease，除非 `--allow-prerelease`。

## 11.5 External CLI Provider

用于 UI UX Pro Max 等。

要求：

- 在临时目录运行；
- 将 HOME/配置目录指向 staging；
- 不让 CLI直接写用户目录；
- 运行后验证输出路径；
- 事务层复制到实际目标；
- 若无法隔离，标记为 `non-transactional` 并要求用户确认；
- 默认 Profile 不得依赖 non-transactional 组件。

## 11.6 Bundled Provider

用于：

- LangChain；
- LangGraph；
- 离线 fallback；
- 本项目原创 Skill。

每个 bundled Skill 必须：

- 有来源声明；
- 有版本；
- 有测试；
- 不重复 GSD 流程；
- 保持 `SKILL.md` 精简；
- 详细资料放 `references/`。

## 11.7 Cache

目录：

```text
~/.ecc-init/cache/
├── archives/
├── extracted/
├── metadata/
└── locks/
```

缓存键：

```text
source_id + resolved_ref + archive_sha256
```

离线模式：

- lock 有缓存：使用缓存；
- lock 无缓存但有 bundled fallback：使用 fallback 并警告；
- required 且无缓存/无 fallback：失败；
- optional 无缓存：跳过并记录。

---

# 12. 事务、备份与回滚

## 12.1 安装事务

状态：

```text
PLANNED
→ PREFLIGHT_OK
→ BACKED_UP
→ EXTERNAL_APPLIED
→ FILES_APPLIED
→ CONFIG_APPLIED
→ VERIFIED
→ COMMITTED
```

失败进入：

```text
FAILED
→ ROLLBACK_ATTEMPTED
→ ROLLED_BACK 或 ROLLBACK_PARTIAL
```

## 12.2 事务目录

```text
~/.ecc-init/operations/<operation-id>/
├── plan.json
├── pre-state.json
├── command-log.json
├── file-journal.json
├── config-journal.json
├── receipt.json
├── rollback-report.json
└── logs/
```

## 12.3 文件写入

- 同目录临时文件；
- flush；
- `os.replace`；
- 写入后计算 hash；
- 保留权限；
- Windows 文件占用时清晰报错；
- 不用非原子覆盖。

## 12.4 文件所有权

每个文件可有多个 owner：

```json
{
  "path": ".claude/skills/python-patterns/SKILL.md",
  "owners": ["pack:python-fastapi"],
  "source": "ecc",
  "sha256": "...",
  "base_sha256": "..."
}
```

删除条件：

1. owners 为空；
2. 当前 hash 等于最后安装 hash；
3. 不属于用户手写；
4. 不被其他组件引用。

否则保留并报告。

## 12.5 外部安装回滚

GSD installer 属于外部操作，处理方式：

- 运行前备份 Claude 配置目录中可能被影响的范围；
- 记录前后文件清单；
- 失败后恢复备份；
- 对无法确认的外部副作用明确标记；
- 不假装完全回滚 npm 缓存等无关副作用。

---

# 13. CLI 设计

## 13.1 兼容入口

保留：

```bash
ecc-init
ecc-init <path>
```

等价于：

```bash
ecc-init init <path> --profile default
```

## 13.2 命令集合

```bash
ecc-init init [path]
ecc-init plan [path]
ecc-init apply <plan.json>
ecc-init status [path]
ecc-init update [path]
ecc-init doctor [path]
ecc-init rollback [path]
ecc-init remove [path]
ecc-init migrate [path]
ecc-init sync-gsd [path]
ecc-init packs list
ecc-init packs show <pack>
ecc-init sources list
ecc-init sources verify
ecc-init workflow status
```

## 13.3 `init`

参数：

```text
--workflow gsd|none
--workflow-version <version>
--workflow-scope global|project
--profile <id>
--pack <id>             可重复
--without-pack <id>     可重复
--offline
--no-sync
--dry-run
--yes
--apply-recommended-config
--allow-prerelease
--json
```

行为：

- 默认 `--workflow gsd`
- 默认 `--profile default`
- 不应静默安装 optional proprietary/custom-license 组件
- 显示：
  - Workflow；
  - Pack；
  - 来源；
  - 版本；
  - 全局写入；
  - 项目写入；
  - 外部命令；
  - 许可证提醒。

## 13.4 `plan`

只生成 InstallPlan：

```bash
ecc-init plan . --profile frontend --output install-plan.json
```

不得修改文件。

## 13.5 `apply`

只能应用：

- schema 合法；
- 路径与当前项目一致；
- 来源 lock 可解析；
- plan 未过期；
- 用户确认的计划。

## 13.6 `status`

显示：

- 当前技术栈；
- Workflow 和版本；
- GSD 是否可用；
- Pack；
- 来源 lock；
- 待应用 GSD 配置；
- 修改过的 managed files；
- 冲突；
- 最近失败操作；
- 可用更新。

## 13.7 `update`

参数：

```text
--workflow
--packs
--source <id>
--check
--dry-run
--yes
```

默认不跨大版本。

## 13.8 `doctor`

检查：

- Python；
- Git；
- Node；
- npm；
- Claude Home；
- 项目权限；
- GSD 安装；
- GSD 版本；
- Pack 文件；
- `SKILL.md` frontmatter；
- GSD `agent_skills` 路径；
- pending config；
- source lock；
- cache；
- hash；
- 冲突；
- symlink；
- Windows 长路径；
- 外部 CLI。

输出 PASS/WARN/FAIL，不把 WARN 全部映射成失败退出码。

## 13.9 `remove`

```bash
ecc-init remove . --pack frontend-essential
ecc-init remove . --workflow
ecc-init remove . --all
```

必须先展示删除计划。

## 13.10 Exit Code

```text
0 成功
1 运行错误
2 存在需人工处理的冲突
3 环境不满足
4 安装计划无效
5 验证失败且已回滚
6 回滚不完整
7 用户取消
```

---

# 14. 技术栈检测

## 14.1 保留现有检测

继续支持：

- Python
- FastAPI
- LangChain
- LangGraph
- TypeScript
- React
- Java
- Spring Boot

## 14.2 新增

优先增加：

- Next.js
- Vite
- Vue
- Node.js
- pytest
- Playwright
- Tailwind CSS
- shadcn/ui

## 14.3 证据模型

每个结果必须有证据：

```json
{
  "stack": "react",
  "confidence": "high",
  "evidence": [
    "package.json dependency react",
    "src/App.tsx"
  ]
}
```

## 14.4 Monorepo

0.2.0：

- 扫描根目录和有限深度；
- 发现 workspace 后报告；
- 不自动向每个子项目安装；
- 提供 `--project-subdir` 或未来 workspace 支持。

不得假装完整支持复杂 monorepo。

---

# 15. 旧版迁移

## 15.1 旧版内容分类

旧版全局 Skill：

- `task-planning`
- `verification-loop`
- `code-review`
- `security-review`
- `code-tour`
- `dev-retrospective`

处理：

| 旧 Skill | 处理 |
|---|---|
| task-planning | 废弃，不再默认注入 |
| verification-loop | 废弃，由 GSD verify 负责 |
| dev-retrospective | 废弃强制流程，保留文件不删除 |
| code-review | 迁移为可选 `ecc-code-review` |
| security-review | 迁移为可选 `ecc-security-review` |
| code-tour | 改为显式辅助，推荐 GSD map-codebase |

## 15.2 全局 CLAUDE.md

旧 managed section 中的主流程规则必须退出。

迁移规则：

1. 识别 `<!-- ecc-init:start global -->`；
2. 备份；
3. 替换为最小说明：
   - GSD 是主工作流；
   - 能力包由项目配置；
   - 不再重复计划规则；
4. 如果用户修改 managed section：
   - 生成迁移 diff；
   - 不强制覆盖；
   - 返回冲突状态。
5. 不动标记外内容。

## 15.3 项目 CLAUDE.md

目标：

- 不再写大中小任务流程；
- 不再要求三阶段复盘；
- 只保留：
  - 项目技术栈；
  - 已安装 Pack；
  - GSD 使用提示；
  - 本项目特殊约束链接。
- 优先让 GSD 使用默认 `.claude/CLAUDE.md`，避免根目录文件污染。
- 旧根 `CLAUDE.md` 只移除本工具 managed section。

## 15.4 旧 Skill

策略：

- 本地未修改且确认由 v1 安装：
  - 可移动到 legacy 备份；
  - 不再激活。
- 已修改：
  - 保留；
  - 标记 `legacy-user-modified`；
  - 不自动删除。
- 同名冲突：
  - 新组件使用 namespaced install name。

## 15.5 State v1 → v2

迁移必须：

- 保留 detection；
- 保留 managed file base；
- 保留 backup；
- 生成 migration report；
- 可重复执行；
- 迁移失败不破坏原 state。

---

# 16. 测试计划

## 16.1 单元测试

### Models

- schema version；
- enum；
- 序列化；
- 无效路径；
- 重复组件；
- unknown fields 策略。

### Pack Resolver

- 依赖排序；
- 环检测；
- 冲突；
- 条件 Pack；
- optional；
- 去重；
- 显式排除优先；
- Profile 合并。

### Source Resolver

- 固定 tag；
- 固定 commit；
- offline；
- cache hit；
- cache miss；
- hash mismatch；
- license missing；
- prerelease 拒绝。

### Archive 安全

- Zip Slip；
- 绝对路径；
- symlink；
- 文件数量上限；
- 大小上限；
- 重复文件；
- 非 UTF-8 文件名；
- Windows 分隔符。

### GSD Adapter

使用 FakeCommandRunner：

- Node 缺失；
- npm 缺失；
- Node 版本过低；
- 成功；
- return code 非 0；
- timeout；
- stderr；
- 已安装同版本；
- 升级；
- 环境变量；
- `shell=False`。

### Agent Policy

- Profile 到 GSD 配置映射；
- minimal/default/frontend/high-assurance；
- 用户显式值保留；
- `task_level=false` 默认；
- `max_concurrent_agents` 范围校验；
- advisory 与 enforceable 字段区分；
- doctor 报告；
- 多 Pack 不增加并发；
- pending config 保留 policy 来源；
- 非 Claude Runtime 不强制 worktree。

### GSD Bridge

- config 不存在；
- pending；
- 数组合并；
- 用户值保留；
- 用户删除不重加；
- 多 owner；
- 卸载；
- malformed JSON；
- atomic write；
- unknown GSD keys 保留。

### Transaction

- 中途异常；
- 文件恢复；
- 新文件删除；
- 用户并发修改；
- rollback partial；
- journal 完整。

### Migration

- 干净 v1；
- 用户修改 Skill；
- 用户修改 CLAUDE section；
- 无 state 但有文件；
- 重复迁移；
- 迁移后 rollback。

## 16.2 集成测试

1. 空 Python 项目 + offline。
2. FastAPI + LangGraph 项目。
3. React + TypeScript 项目。
4. Java + Spring 项目。
5. 已存在 CLAUDE.md。
6. 已存在 GSD config。
7. GSD config 尚未初始化。
8. 多 Pack 共享 Skill。
9. update 后 local change。
10. remove Pack。
11. rollback。
12. Windows 风格路径。
13. `CLAUDE_HOME` 自定义。
14. `ECC_INIT_HOME` 自定义。
15. 网络失败 fallback。

## 16.3 E2E

真实网络 E2E 不进入普通单元测试。

标记：

```python
@pytest.mark.network
@pytest.mark.e2e
```

场景：

- 固定版本 GSD 安装到临时 Claude Home；
- 固定 commit Skill 下载；
- UI UX CLI staging；
- `doctor` 验证；
- 完整 remove。

CI 中：

- 普通 PR 不运行网络 E2E；
- nightly 或手动 workflow 运行。

## 16.4 平台矩阵

- Windows 11
- Ubuntu latest LTS
- macOS latest runner
- Python 3.10、3.11、3.12、3.13
- Node 22、24
- Git 当前稳定版

Windows 必测：

- 盘符；
- 空格路径；
- PowerShell；
- 文件占用；
- 长路径；
- CRLF；
- `where node`；
- `npx.cmd` 解析。

## 16.5 质量门

每个 PR：

```bash
python -m pytest
python -m compileall src
```

建议新增：

```bash
ruff check .
mypy src/ecc_init
```

但新增依赖需单独决定。第一阶段不得因引入完整工具链阻塞架构迁移。

---

# 17. 实施阶段

以下每个阶段都包含目标、任务、产出和验收。不得前详后略。

---

## 阶段 0：冻结基线和建立保护

### 目标

确认现有行为，防止重构破坏已有功能。

### 任务

1. 创建开发分支：
   ```bash
   git checkout -b refactor/gsd-workflow-platform
   ```
2. 运行完整测试并记录。
3. 补足当前缺失的回归测试：
   - offline init；
   - CLAUDE.md 保留；
   - Skill 冲突；
   - rollback；
   - status；
   - doctor。
4. 保存现有生成结构 fixture。
5. 在 README 标记：
   - 0.1.x legacy；
   - 0.2.0 将切换为 GSD 内核。
6. 修正 `pyproject.toml` 中错误的 Repository URL，使其指向本仓库，而不是 ECC。
7. 新增 `CHANGELOG.md`。
8. 新增本计划文件到仓库。

### 产出

- 基线测试；
- fixtures；
- changelog；
- 正确项目元数据。

### 验收

- 当前功能测试全部通过；
- 没有改变用户生成结果；
- `git diff` 只包含测试、文档和元数据；
- 可在 Windows 路径运行测试。

---

## 阶段 1：核心模型、Plan 和 State v2

### 目标

建立后续功能的稳定数据结构，不接入真实 GSD。

### 新建文件

```text
src/ecc_init/core/models.py
src/ecc_init/core/plan.py
src/ecc_init/core/state_store.py
src/ecc_init/core/receipt.py
src/ecc_init/core/validation.py
src/ecc_init/errors.py
```

### 任务

1. 定义：
   - SourceSpec；
   - ComponentSpec；
   - PackSpec；
   - WorkflowSpec；
   - InstallPlan；
   - Operation；
   - Receipt；
   - CheckResult。
2. 定义 schema version。
3. 实现 JSON 序列化。
4. 实现原子 StateStore。
5. 实现 operation ID。
6. 实现 plan JSON 输出。
7. CLI 增加：
   ```bash
   ecc-init plan
   ```
   第一版可只输出 legacy 行为对应 Plan。
8. 不改变 `initialize_project` 默认行为。
9. 添加完整测试。
10. 设计错误类型：
    - ConfigError；
    - EnvironmentError；
    - SourceError；
    - IntegrityError；
    - ConflictError；
    - TransactionError；
    - MigrationError。

### 验收

- 所有模型有 round-trip 测试；
- 无效 manifest 清晰报错；
- State 写入原子；
- legacy init 仍通过；
- `ecc-init plan --json` 不改文件；
- 不新增外部依赖。

---

## 阶段 2：声明式 Registry 和 Pack Resolver

### 目标

把“安装哪些东西”从 `app.py` 硬编码迁移到 Manifest。

### 新建

```text
src/ecc_init/packs/
src/ecc_init/resources/registry/
```

### 任务

1. 实现 Registry Loader。
2. Manifest schema 校验。
3. 创建 Workflow：
   - `none`
   - `gsd`，先只声明不执行。
4. 创建 Pack：
   - project-baseline；
   - quality-basic；
   - python-fastapi；
   - rag-python；
   - java-spring；
   - frontend-essential。
5. 创建 Profile：
   - minimal；
   - default；
   - frontend；
   - rag。
6. 实现依赖拓扑排序。
7. 实现冲突检测。
8. 实现 stack condition。
9. 把旧 `manifest.json` 转换或兼容读取。
10. `ecc-init packs list/show`。
11. `ecc-init plan` 输出解析后的 Pack。
12. 保留旧 `initialize_project`，但新代码路径可通过 feature flag 运行。

### 验收

- 解析顺序稳定；
- 相同输入生成字节稳定的 Plan；
- 循环依赖有明确错误；
- Profile 可覆盖；
- 用户排除 Pack 生效；
- 未实际执行外部安装。

---

## 阶段 3：事务和文件所有权

### 目标

让后续外部组件安装可回滚。

### 新建

```text
src/ecc_init/core/transaction.py
src/ecc_init/core/ownership.py
src/ecc_init/core/receipt.py
```

### 任务

1. 把现有 BackupSession 接入 Transaction。
2. 引入 file journal。
3. 引入 config journal。
4. 实现 owner。
5. 实现共享文件引用。
6. 实现 failure injection 测试。
7. 扩展 rollback：
   - operation ID；
   - latest；
   - 指定 receipt。
8. `status` 显示用户修改 managed file。
9. 保持现有三方 merge。
10. 明确 external operation 的回滚边界。

### 验收

- 任一步失败可恢复；
- 新文件、修改文件、删除文件均可恢复；
- 用户并发修改不被覆盖；
- rollback partial 有退出码和报告；
- receipt 完整。

---

## 阶段 4：Source Provider 和来源锁

### 目标

安全、确定地获取外部 Skill。

### 新建

```text
src/ecc_init/sources/
```

### 任务

1. Bundled Provider。
2. GitHub Archive Provider。
3. Directory projection。
4. Cache。
5. SHA256。
6. License collection。
7. Source lock。
8. Offline。
9. Host allowlist。
10. archive 安全。
11. 先接入 ECC 固定目录。
12. 再接入 Vercel 固定目录。
13. 不接 UI UX CLI，留到前端阶段。
14. 不接 Anthropic，自定义许可证留到 optional installer。

### 验收

- 固定 commit 可重复安装；
- 网络失败使用 lock/cache；
- hash 不匹配失败；
- Zip Slip 测试；
- 来源和许可证可查询；
- `ecc-init sources verify` 可用。

---

## 阶段 5：GSD Workflow Adapter

### 目标

以官方固定版本 GSD 取代旧主流程。

### 新建

```text
src/ecc_init/workflows/base.py
src/ecc_init/workflows/registry.py
src/ecc_init/workflows/gsd.py
src/ecc_init/workflows/none.py
```

### 任务

1. CommandRunner 抽象。
2. 环境检查。
3. Node/npm 版本检查。
4. 固定 GSD 版本。
5. dry-run 外部命令。
6. GSD install。
7. inspect。
8. verify。
9. update。
10. remove 策略。
11. 记录命令输出。
12. 备份 Claude Home 受影响范围。
13. 默认 Workflow 改为 GSD，但只在迁移提示通过后启用。
14. 旧模式保留临时参数：
    ```bash
    ecc-init init --legacy
    ```
    只保留一个小版本，随后删除。
15. README 更新安装前提。

### 验收

- Fake Runner 全覆盖；
- Node 缺失不改文件；
- Node 过低清晰报错；
- 同版本幂等；
- 安装 receipt；
- 不复制 GSD 源码；
- 不修改 GSD 文件；
- 真实 E2E 可在临时 Claude Home 安装。

---

## 阶段 6：GSD 配置桥

### 目标

让 Pack 精确注入 GSD Agent。

### 新建

```text
src/ecc_init/packs/gsd_bridge.py
```

### 任务

1. 读取 `.planning/config.json`。
2. 实现 AgentPolicyProfile：
   - minimal；
   - default；
   - frontend；
   - high-assurance。
3. 将可硬性配置字段映射到 GSD：
   - `parallelization.enabled`；
   - `plan_level`；
   - `task_level`；
   - `skip_checkpoints`；
   - `max_concurrent_agents`；
   - `min_plans_for_parallel`；
   - `workflow.use_worktrees`；
   - `workflow.subagent_timeout`；
   - `workflow.node_repair_budget`。
4. 明确标记 advisory-only：
   - Phase 累计调用预算；
   - Token/费用预算；
   - 角色次数。
5. `doctor` 必须分别报告 hard-enforced 和 advisory-only。
6. Pack Resolver 不得因 Pack 数量自动提高并发。
7. 用户显式配置优先。


8. pending config。
9. deep merge。
10. agent_skills 合并。
11. owner。
12. config default。
13. 用户删除保护。
14. `sync-gsd`。
15. `doctor` 路径验证。
16. 卸载 Pack 清理。
17. 输出配置 diff。
18. 不允许路径穿越。
19. Skill 目录必须有 `SKILL.md`。

### 验收

- GSD 未初始化时不失败；
- 初始化后可一键 sync；
- 用户配置不丢；
- 数组无重复；
- 多 Pack 卸载正确；
- malformed JSON 不覆盖；
- 所有操作可回滚。

---

## 阶段 7：Legacy v1 迁移

### 目标

安全退出旧自研流程。

### 新建

```text
src/ecc_init/migration/legacy_v1.py
src/ecc_init/migration/reports.py
```

### 任务

1. 检测 v1。
2. 生成迁移 Plan。
3. 移除旧主流程 managed section。
4. 废弃三个旧流程 Skill。
5. 用户修改保护。
6. 保留 docs。
7. 迁移 Skill 为 namespaced Pack。
8. state v2。
9. migration report。
10. rollback。
11. `ecc-init migrate --dry-run`。
12. `init` 自动提示迁移。

### 验收

- 干净 v1 自动迁移；
- 修改版 v1 不被覆盖；
- 迁移可重复；
- 可回滚；
- 迁移后不再有两套主流程；
- GSD 成为唯一流程权威。

---

## 阶段 8：Frontend Pack

### 目标

形成完整前端设计、实现、验证组合。

### 任务

1. 接入 Vercel Skills。
2. 实现 UI UX Pro Max staging adapter。
3. 配置 GSD UI Agents。
4. React 条件注入。
5. GSD UI config defaults。
6. optional Anthropic Source policy。
7. 检测 Playwright。
8. 检测 GSD Browser。
9. `doctor` 输出前端工具状态。
10. 文档展示标准生命周期：
    ```text
    /gsd-discuss-phase N
    /gsd-ui-phase N
    /gsd-plan-phase N
    /gsd-execute-phase N
    /gsd-verify-work N
    /gsd-ui-review N
    ```
11. 验证 Skill 不把主流程规则重复写入。
12. 示例项目 E2E。

### 验收

- React 项目得到正确 Skill；
- 非前端项目不安装；
- UI Agent 映射正确；
- GSD config 不覆盖用户；
- UI UX Pro Max 安装可回滚；
- optional 组件失败不破坏 required 组件；
- 来源/许可证完整。

---

## 阶段 9：技术栈 Pack

### 目标

完成 Python、RAG、Java 能力包。

### 任务

1. ECC 来源固定。
2. Python/FastAPI。
3. LangChain/LangGraph bundled。
4. Java/Spring。
5. 每个 Skill 清除重复流程指令。
6. 添加 Skill frontmatter 测试。
7. 每个 Pack Agent 映射。
8. 更新 stack detector。
9. 离线 fallback。
10. Skill 内容版本化。

### 验收

- 自动检测正确；
- Pack 不重复；
- 离线可用；
- upstream 更新不覆盖用户修改；
- 每个 Skill 只负责领域知识；
- GSD Agent 注入可验证。

---

## 阶段 10：CLI、Update、Remove 和 Doctor 完整化

### 目标

把框架变成可长期维护工具。

### 任务

1. 完整 CLI。
2. JSON 输出。
3. dry-run。
4. update check。
5. source update。
6. workflow update。
7. Pack update。
8. remove。
9. doctor。
10. 冲突报告。
11. 退出码。
12. PowerShell 文档。
13. 错误信息。
14. 无堆栈默认输出，`--debug` 显示堆栈。
15. 支持非交互 `--yes`。
16. 支持 CI。

### 验收

- 所有命令有 help；
- JSON 可机器解析；
- dry-run 无写入；
- remove 安全；
- update 可预览；
- Windows 可用；
- 文档示例通过 smoke test。

---

## 阶段 11：安全、CI 和发布

### 目标

发布 0.2.0 Alpha。

### 任务

1. GitHub Actions：
   - Python matrix；
   - OS matrix；
   - unit/integration；
   - package build；
   - wheel install；
   - CLI smoke。
2. nightly network E2E。
3. archive 安全测试。
4. subprocess 注入测试。
5. symlink 测试。
6. package data 完整性。
7. LICENSE/NOTICE。
8. README。
9. MIGRATION.md。
10. ARCHITECTURE.md。
11. SOURCE_POLICY.md。
12. SECURITY.md。
13. 发布 dry-run。
14. tag。
15. pipx 安装测试。

### 验收

- wheel 包含 Manifest 和 bundled Skill；
- 不包含禁止再分发的 Anthropic 内容；
- 所有平台绿；
- 0.1 → 0.2 迁移文档完整；
- 安装、更新、卸载和回滚均有演示。

---

# 18. 完整验收场景

## 场景 A：全新 FastAPI + LangGraph 项目

执行：

```bash
ecc-init init . --profile default
```

期望：

- 安装/确认 GSD；
- 安装 Python、FastAPI、LangChain/LangGraph Skill；
- 写 pending GSD config；
- 用户运行 `/gsd-new-project`；
- `ecc-init sync-gsd` 后 Agent 注入生效；
- 无旧 task-planning。

## 场景 B：React 项目

期望：

- frontend-essential；
- UI UX Pro Max；
- Vercel Skills；
- GSD UI Phase/Review；
- React Skill 仅给 executor/reviewer；
- 非 React Skill 不安装。

## 场景 C：已有 GSD

期望：

- 识别版本；
- 同版本不重复；
- 只装 Pack；
- 合并 config；
- 不覆盖 GSD 文件。

## 场景 D：旧 ecc-init 用户

期望：

- 显示迁移；
- 备份；
- 退出旧流程；
- 用户自定义保留；
- 可 rollback。

## 场景 E：离线

期望：

- 已缓存组件使用缓存；
- bundled 使用本地；
- optional 跳过；
- required 缺失清晰失败；
- 不产生半安装。

## 场景 F：用户修改 Skill

期望：

- update 三方合并；
- 冲突保留本地；
- 生成 upstream/diff；
- 状态显示需处理。

## 场景 G：GSD config 用户显式关闭 UI Review

期望：

- frontend Pack 不改回 true；
- 仍可安装 Skill；
- doctor 提示 UI Review 关闭，但不报错。

## 场景 H：卸载 Pack

期望：

- 只移除自身 Agent 绑定；
- 保留其他 Pack 共享项；
- 用户修改文件不删；
- receipt 更新。

## 场景 I：外部 CLI 中途失败

期望：

- 不复制 staging 半成品；
- 回滚；
- command log；
- 非 0 退出。

## 场景 J：Windows 路径含中文和空格

期望：

- subprocess 参数正确；
- 路径正确；
- 无 shell quoting 错误；
- rollback 正常。

---

# 19. 许可证和供应链要求

1. 每个 Source 必须有：
   - repository；
   - resolved ref；
   - license；
   - hash；
   - source path。
2. MIT 文件保留 attribution。
3. 自定义许可证组件不打包。
4. 外部 CLI 声明 executable surface。
5. 更新时比较：
   - 新增 hooks；
   - 新增 commands；
   - 新增 scripts；
   - 新增 binary；
   - 新增网络调用。
6. executable surface 变化必须重新确认。
7. 不接受模糊相似包名。
8. GSD 包名固定为：
   ```text
   @opengsd/gsd-core
   ```
9. npm 安装失败不得尝试同名替代包。
10. source lock 应进入项目版本控制，但不得包含 secret。
11. cache 不进入项目版本控制。
12. `.planning/config.json` 可能包含 API key 时，工具输出必须脱敏。

---

# 20. 风险清单

## 风险 1：GSD 上游快速变化

应对：

- 版本 pin；
- Adapter；
- contract test；
- nightly；
- 不修改源码。

## 风险 2：两个安装器同时写 Claude Home

应对：

- 备份；
- snapshot；
- receipt；
- GSD 官方 installer；
- 不自行复制内部文件。

## 风险 3：能力包上下文膨胀

应对：

- 只绑定需要的 Agent；
- Skill progressive disclosure；
- 不把全部资料注入；
- 避免巨大 AGENTS.md 作为启动记忆。

## 风险 4：用户配置被覆盖

应对：

- default-only；
- 三方 merge；
- ownership；
- config diff；
- rollback。

## 风险 5：外部脚本供应链风险

应对：

- allowlist；
- pin；
- hash；
- staging；
- executable audit；
- explicit consent。

## 风险 6：项目定位重新膨胀

应对：

- 不做自己的 Harness；
- 不实现子 Agent Runtime；
- 不实现模型路由；
- 不实现 GSD 已有功能；
- Context Refresh 延后。

## 风险 7：Windows 不兼容

应对：

- 不使用 shell 拼接；
- CI Windows；
- `npx.cmd`；
- path tests；
- atomic file fallback。

---

# 21. Definition of Done

0.2.0 Alpha 完成必须满足：

1. GSD 是默认且唯一主工作流。
2. 现有仓库未 Fork GSD。
3. GSD 使用固定版本官方安装。
4. 有 Workflow Adapter。
5. 有声明式 Pack。
6. 有 Source Lock。
7. 有 Receipt。
8. 有 Dry Run。
9. 有完整 Rollback。
10. 有 v1 Migration。
11. 有 GSD Agent Skill 注入。
12. 有 frontend-essential。
13. 有 Python/FastAPI/RAG/Java/Spring Pack。
14. 不再默认安装旧流程 Skill。
15. 用户修改不被覆盖。
16. offline 有确定行为。
17. Windows、Linux、macOS CI。
18. 许可证记录完整。
19. README、ARCHITECTURE、MIGRATION、SOURCE_POLICY 完整。
20. 所有验收场景有自动测试或明确手工 E2E 记录。

---

# 22. 第一轮实际开发任务

Codex 在第一次执行本计划时，只做以下内容：

## Task 0：确认开发基座与 Codex 约束

1. 确认当前目录为现有 `ecc-init` Git 仓库。
2. 输出：
   ```bash
   git status --short
   git branch --show-current
   git log -5 --oneline
   ```
3. 不创建替代仓库。
4. 创建或合并根 `AGENTS.md`。
5. 创建或合并 `.codex/config.toml`：
   ```toml
   [agents]
   max_threads = 3
   max_depth = 1
   job_max_runtime_seconds = 900
   ```
6. 创建 `docs/internal/IMPLEMENTATION_STATUS.md`。
7. 第一轮不使用并行写 Agent。

## Task 1：仓库盘点

输出：

```text
docs/internal/CURRENT_ARCHITECTURE.md
```

内容：

- 当前文件树；
- 当前 CLI；
- 当前状态；
- 当前安装流程；
- 当前测试；
- 与本计划差异。

## Task 2：测试基线

补齐阶段 0 测试，不改行为。

## Task 3：元数据修复

- Repository URL；
- CHANGELOG；
- version 决策不立即升版本，直到架构代码落地。

## Task 4：核心 Models

实现阶段 1 中最小模型。

## Task 5：Plan 命令骨架

`ecc-init plan` 输出 legacy 安装计划，不写文件。

## Task 6：验证

```bash
python -m pytest
python -m compileall src
```

## 第一轮停止条件

完成以上任务后停止，报告：

- 修改文件；
- 测试；
- `git diff --check`；
- 使用过的子 Agent、角色、结果和重试次数；
- 未完成；
- 风险；
- 下一阶段建议。

第一轮子 Agent预算：

```text
只读 explorer：最多 1
只读 reviewer：最多 1
并行 write worker：0
递归子 Agent：0
```

不得在同一轮直接安装真实 GSD 或大规模移动文件。

---

# 23. 给 Codex 的推荐启动提示

将本文件保存为仓库根目录 `DEVELOPMENT_PLAN_CODEX.md` 后，可在 Codex 中输入：

```text
请完整阅读 DEVELOPMENT_PLAN_CODEX.md、根目录 AGENTS.md（如已存在）以及当前仓库源码，并严格按照“0. Codex 执行契约”“0A. Codex 开发侧子 Agent 治理”和“22. 第一轮实际开发任务”开始实施。

要求：
1. 确认当前工作目录就是现有 yuyukosama2004/ecc-init 仓库，不创建替代仓库；
2. 先阅读当前仓库全部核心源码和测试；
3. 先运行现有测试并记录预先存在的失败；
4. 不要 Fork、vendor、复制或修改 GSD；
5. 不要一次性实施全部阶段；
6. 第一轮只完成阶段 0、阶段 1规定的最小范围；
7. 第一轮不得使用并行写子 Agent；最多一个只读 explorer 和一个只读 reviewer；
8. 每一项修改都必须有测试；
9. 完成后运行完整 pytest、compileall、git diff --check 和 git diff；
10. 更新 docs/internal/IMPLEMENTATION_STATUS.md；
11. 给出实际 diff 摘要、测试证据、风险和未完成项；
12. 不要把计划内容当成已存在的事实，先核对仓库。
```

---

# 24. 最终产品使用示例

## 默认初始化

```bash
ecc-init init .
```

## 预览

```bash
ecc-init plan . --profile default
```

## 前端项目

```bash
ecc-init init . --profile frontend
```

## RAG 项目

```bash
ecc-init init . --profile rag
```

## 自定义

```bash
ecc-init init . \
  --workflow gsd \
  --pack python-fastapi \
  --pack rag-python \
  --without-pack frontend-essential
```

## 离线

```bash
ecc-init init . --offline
```

## GSD 初始化后同步

```bash
ecc-init sync-gsd .
```

## 状态

```bash
ecc-init status .
```

## 更新预览

```bash
ecc-init update . --check
```

## 移除 Pack

```bash
ecc-init remove . --pack frontend-essential
```

## 回滚

```bash
ecc-init rollback .
```

---


# 24A. Codex 实施依据与注意事项

本计划针对 Codex 的执行约束依据以下官方能力设计：

- Codex 在开始工作前读取 `AGENTS.md`，并按全局到项目、目录逐级合并；因此本仓库使用短 `AGENTS.md` 存稳定规则，长计划单独保存。
- Codex 子 Agent不会无条件自动创建；本计划只有在明确符合规模和并行条件时才授权。
- Codex 支持：
  - `agents.max_threads`
  - `agents.max_depth`
  - `agents.job_max_runtime_seconds`
- 官方默认并发上限可能高于本项目需求；本项目主动采用更保守的 `max_threads = 3`。
- 官方建议优先把并行 Agent用于只读探索、测试和分析，谨慎并行写代码；本计划进一步要求文件所有权和 worktree。
- 自动化时优先使用显式 sandbox，不使用宽泛的 full access。
- Codex 非交互执行可用于 CI，但 0.2.0 阶段不把 Codex 本身作为产品运行时依赖。

官方参考：

```text
https://developers.openai.com/codex/guides/agents-md
https://developers.openai.com/codex/concepts/subagents
https://developers.openai.com/codex/subagents
https://developers.openai.com/codex/learn/best-practices
https://developers.openai.com/codex/noninteractive
```

这些链接用于 Codex 开发方式，不代表最终 `ecc-init` 用户必须安装或使用 Codex。


# 25. 最终架构结论

本项目采用“保留壳、替换核心”的路线：

```text
保留：
  Python CLI
  技术栈检测
  文件合并
  备份回滚
  离线缓存
  状态管理基础

替换：
  自研主流程
  全局流程 Skill
  强制复盘规则
  模糊的自动触发

引入：
  GSD Core
  Workflow Adapter
  Pack Registry
  Source Provider
  GSD Agent Skill Bridge
  Receipt 和 Source Lock
  前端 UI 设计/验证能力

不引入：
  GSD Fork
  完整 ECC
  双工作流
  自研 Agent Runtime
```

最终关系：

```text
ecc-init = 管理器
GSD Core = 工作流内核
ECC/Vercel/UI UX/Anthropic = 受控能力来源
GSD agent_skills = 连接机制
Receipt/Lock/Transaction = 安装可靠性基础
```

本计划完成后，`ecc-init` 不再是“几份 Prompt 的初始化器”，而是一个：

> **可审计、可组合、可更新、可回滚，以 GSD 为流程内核的 Claude Code 开发框架管理器。**
