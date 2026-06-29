---
name: code-tour
description: 第一次进入陌生项目且 `.claude/ecc-init-state.json` 中 code_tour_completed=false 时自动使用。生成面向开发者的项目结构、入口、调用链和技术栈概览，并更新 docs/PROJECT_OVERVIEW.md。
metadata:
  origin: ECC-inspired-customized
---

# 项目代码导读

本 Skill 生成 Markdown 项目概览，不生成 `.tour` JSON，也不修改业务代码。

## 触发条件

- 第一次处理当前项目；或
- ecc-init 因项目结构明显变化将 `code_tour_completed` 重置为 `false`。

已完成且结构无明显变化时不要重复执行。

## 阅读顺序

1. README、项目清单和依赖文件。
2. 顶层目录与主要模块。
3. 应用启动入口和配置加载。
4. 一条核心请求、任务或数据处理链路。
5. 数据库、缓存、队列、向量库或外部 API。
6. 测试目录和常用命令。
7. 已知风险、未完成部分和需要用户确认的假设。

## 输出文件

更新 `docs/PROJECT_OVERVIEW.md`，至少包含：

- 项目目标；
- 技术栈及识别依据；
- 目录结构和模块职责；
- 启动入口；
- 核心调用链；
- 配置、数据存储和外部依赖；
- 启动、测试、Lint 与构建命令；
- 初学者阅读顺序；
- 风险与待确认事项。

所有路径和代码位置必须真实存在，不猜测行号。完成后将 `.claude/ecc-init-state.json` 的 `code_tour_completed` 改为 `true`。
