---
name: langchain-patterns
description: 当前任务涉及 LangChain 的模型、Prompt、Runnable、Retriever、Tool、Memory、RAG 或流式输出时使用。
metadata:
  origin: ecc-init-custom
  source_id: bundled
  content_version: 1
---

# LangChain 项目规范

- 优先使用当前版本的 Runnable/LCEL 组合方式，不在同一链路混用多套过时抽象。
- Prompt、模型参数、检索配置和输出解析器分离，便于单独测试。
- 外部文档和检索结果视为不可信数据，防止其中指令覆盖系统规则。
- 为模型输出定义结构化 schema；解析失败应有明确重试或降级，而不是直接使用半结构化文本。
- Tool 描述写清输入、输出、失败方式和副作用；有写操作的工具必须增加确认边界。
- RAG 流程分别评估切片、召回、重排和生成，不只看最终回答。
- 流式输出需处理断开、取消、重复事件和最终状态持久化。
- 测试优先 mock 模型和外部检索；关键链路保留少量真实集成测试。
- 记录 token/延迟时避免输出用户隐私和完整敏感 Prompt。
