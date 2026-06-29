---
name: langgraph-patterns
description: 当前任务涉及 LangGraph 状态、节点、边、条件路由、checkpoint、interrupt、恢复或多 Agent 图时使用。
metadata:
  origin: ecc-init-custom
---

# LangGraph 项目规范

- 先定义状态 schema，再定义节点；状态字段要有清楚所有权和合并语义。
- 节点保持单一职责，输入和输出只包含必要状态更新，不偷偷修改外部全局状态。
- 条件路由必须覆盖未知值和失败分支，避免图进入不可恢复状态。
- 将业务重试与基础设施重试区分；为每种重试设置上限和可观测信息。
- 使用 checkpoint 时明确 thread/session 标识、持久化范围和敏感数据处理。
- interrupt 前保存恢复所需状态；恢复后保证幂等，避免重复写数据库或重复调用付费 API。
- Tool/节点副作用需要可追踪，涉及依赖、数据库迁移或不可逆写入时先向用户确认。
- 流式事件定义稳定类型，前端不要依赖临时字符串。
- 测试覆盖：正常路径、每个条件分支、中断恢复、节点失败、达到重试上限和重复恢复。
