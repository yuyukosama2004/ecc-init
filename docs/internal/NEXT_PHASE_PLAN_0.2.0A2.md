# 0.2.0a2 改进计划

> 基于 2026-07-08 novelflow 项目实战验证的痛点分析

## 版本目标

从 0.2.0a1（单项目 scope、手动全局组件）升级到支持多 scope apply、更好的新手体验、更少的文档查阅需求。

## P0 — 阻断性改进

### 1. apply 支持全局 scope 组件写入

**现状**：global scope 组件（skill-code-review 等）被跳过，用户需手动复制。

**目标**：
- `apply plan.json --yes` 同时写入 project 和 global scope 组件
- global 组件安装到 `~/.claude/skills/<name>/SKILL.md`
- 与 project 组件共用同一 Transaction、Source Lock、Receipt
- 保持"默认 project-only，显式启用 global"的安全策略

**具体改动**：
- `installer.py`: 移除 `if component.target_scope != "project": continue` 阻塞逻辑
- 新增 `--scope` 参数：`project`（默认）、`global`、`all`
- global 写入路径使用 `AppPaths.claude_home` 而非 `project_root/.claude`
- 全局文件的 rollback 操作也需要 transaction 保护
- CLI 输出区分 project/global 来源

### 2. GSD post-install 自动化

**现状**：用户跑完 `ecc-init gsd install --yes` 后需手动执行 `gsd-core --claude --global`。

**目标**：
- `ecc-init gsd install --yes` 完成后自动调用 `gsd-core --<runtime> --<scope>`
- 或至少显式提示用户需要执行的下一步命令（当前已有 warning 但不够醒目）
- `installed_unverified` 状态提供清晰的下一步指令

**具体改动**：
- `GsdWorkflowAdapter.install()` 成功后自动运行注册命令
- 添加 `--skip-registration` 标志允许跳过自动注册
- 失败时明确报错，不静默跳过

### 3. 新手引导完善

**现状**：用户从零开始需要查阅多个文档才能完成完整流程。

**目标**：`ecc-init init .` 输出完整的下一步指引。

**具体改动**：
- init 输出包含 checklist：1) 安装 GSD → 2) 迁移旧项目 → 3) apply packs → 4) 注册全局 skills
- 根据当前项目状态动态显示相关步骤（已有 GSD 则跳过步骤 1）
- `doctor` 新增 `--mode quickstart` 输出新手友好的一步步指引

## P1 — 体验改进

### 4. 迁移流程改善

**现状**：旧项目 apply 直接报错 `legacy schema`，用户需要另外跑 migrate 命令。

**目标**：
- `apply` 检测到 legacy v1 时自动提示迁移命令
- 可选 `apply --auto-migrate` 在 apply 之前自动执行迁移
- migrate 完成后可直接 continue apply 而不必重新输入

### 5. plan/apply 一体命令

**现状**：用户需要分三步：`plan` → `apply --dry-run` → `apply --yes`

**目标**：添加便捷命令 `ecc-init setup . --yes` 一键完成 plan + apply。

**具体改动**：
- 新增 `ecc-init setup` 子命令
- 内部串联 plan → apply（默认 dry-run，需 `--yes` 写入）
- 支持所有 plan 和 apply 的参数透传

### 6. 更好的 init 输出

**现状**：`init --yes` 输出技术细节多，但用户不知道"接下来干什么"。

**目标**：
- 输出添加分段标题和图标
- 分离"已完成"和"下一步"区域
- 用表格展示 pack 安装状态和对应 skill 列表

## P2 — 架构完善

### 7. `.planning/config.json` 引导创建

**现状**：apply 只能在已有 config 上 sync，不能创建。

**目标**：
- 提供 `ecc-init gsd init-project` 引导用户初始化 GSD 项目配置
- 或检测到缺少 config 时输出清晰的 GSD 初始化指引
- 继续遵循"不自动创建 config"原则，但提供更好的引导

### 8. 回滚改进

**现状**：rollback 按 operation-id 回滚，但全局组件不在回滚范围内。

**目标**：
- 全局组件也纳入 transaction 管理
- rollback 支持 project + global 的双路径回滚
- 回滚报告区分 project/global 来源

### 9. 源更新支持

**现状**：`update --sources` 是 preview-only，不实际拉取。

**目标**：
- `update --sources --yes` 实际拉取远程源更新
- 对比 source lock 中的版本与 registry 声明
- 更新后重新 lock

## 优先级排序

| 优先级 | 条目 | 预估工作量 | 影响范围 |
|---|---|---|---|
| P0 | apply 支持全局 scope | 中 | installer, CLI, rollback, tests |
| P0 | GSD post-install 自动化 | 小 | workflows/gsd.py, CLI |
| P0 | 新手引导完善 | 中 | init, doctor, status CLI |
| P1 | 迁移流程改善 | 小 | apply CLI, migration |
| P1 | plan/apply 一体命令 | 小 | 新 setup 子命令 |
| P1 | 更好的 init 输出 | 小 | CLI 输出格式化 |
| P2 | .planning/config.json 引导 | 小 | GSD bridge, CLI |
| P2 | 回滚改进 | 中 | transaction, rollback |
| P2 | 源更新支持 | 大 | sources, update CLI |

## 不在范围内

- 新 Pack（保持现有 6 个）
- 真实 ECC/Vercel/Anthropic 外部源安装
- GitHub archive 目录投影（多文件）
- `remove --pack X --files --yes` 文件级删除
- codex/cursor runtime 正式支持

## 参考

- [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) — 0.2.0a1 完成度评估
- [apply-packs.md](../how-to/apply-packs.md) — 当前 apply 文档
- [install-gsd.md](../how-to/install-gsd.md) — 当前 GSD 安装文档
