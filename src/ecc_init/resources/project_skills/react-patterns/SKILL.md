---
name: react-patterns
description: 当前任务涉及 React 组件、Hooks、状态、表单、请求、渲染性能或组件测试时使用。
metadata:
  origin: ecc-init-fallback
  source_id: ecc-upstream-pinned
  content_version: 1
---

# React 项目规范

- 组件保持职责集中；优先组合而不是过深 prop drilling 或过早抽象。
- state 只保存无法从 props/其他 state 推导的值。
- `useEffect` 只处理外部同步，依赖项完整；避免用 effect 模拟普通计算。
- 异步请求处理 loading、error、空数据、取消和竞态。
- 列表使用稳定业务键，不用可能重排的数组下标。
- 表单在提交边界进行运行时校验，并明确服务端错误展示。
- 不为了“性能”无证据地到处使用 memo；先定位真实重渲染或昂贵计算。
- 测试关注用户可见行为和关键交互，避免过度依赖组件内部实现。
