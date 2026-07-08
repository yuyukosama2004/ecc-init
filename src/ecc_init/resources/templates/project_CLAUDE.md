<!-- ecc-init:start project -->
# 当前项目补充规则

## 自动识别结果

- 技术栈：{{DETECTED_STACKS}}

## 可用项目 Skill

{{PROJECT_SKILLS}}

仅在任务实际涉及对应技术栈时调用相关 Skill，避免无关规则进入上下文。

## 项目命令

{{PROJECT_COMMANDS}}

执行命令前仍需读取项目配置确认命令真实存在；不要仅根据本段猜测。

## 首次代码导读

读取 `.claude/ecc-init-state.json`。如果 `code_tour_completed` 为 `false`：

1. 使用 `code-tour` 梳理项目目标、目录、入口、调用链、配置、数据层和外部依赖。
2. 更新 `docs/PROJECT_OVERVIEW.md`。
3. 将 `code_tour_completed` 改为 `true`。

## 项目约束

- 优先沿用当前项目已有目录结构、命名、框架惯例和测试方式。
- 不把其他 Demo 的架构习惯生搬到当前项目。
- 技术栈 Skill 与实际代码冲突时，以当前项目已有约定为准，并说明差异。

## Agent 使用约束

{{AGENT_POLICY}}

上述 agent 约束优先级高于 Skill 或工作流中的默认配置。违反约束前必须向用户确认。
<!-- ecc-init:end project -->
