---
name: typescript-patterns
description: 当前任务涉及 TypeScript 类型、Node.js 或前端业务代码时使用。强调边界校验、窄类型和项目现有配置。
metadata:
  origin: ecc-init-custom
---

# TypeScript 项目规范

- 读取 `tsconfig.json` 和现有 ESLint/格式化配置，不擅自改变严格度。
- 外部输入先通过 schema 或明确校验收窄，不能仅靠类型断言。
- 避免无依据的 `any`、双重断言和非空断言；确需使用时说明原因。
- 使用可辨识联合表达状态，避免多个布尔值形成非法组合。
- 异步调用处理失败、超时和取消；并行任务使用 `Promise.all` 前确认失败语义。
- 公共函数和组件 props 保持稳定、清晰，不暴露不必要的内部类型。
- 新功能补充单元测试，并覆盖类型无法表达的运行时边界。
