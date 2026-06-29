---
name: springboot-patterns
description: 当前任务涉及 Spring Boot Controller、Service、Repository、Security、事务、配置或测试时使用。
metadata:
  origin: ecc-init-fallback
---

# Spring Boot 项目规范

- Controller 负责协议和校验，Service 负责业务，Repository 负责持久化；沿用现有分层。
- 使用构造器注入，避免字段注入和隐式依赖。
- DTO 与持久化实体边界清晰，不直接把敏感实体字段暴露给接口。
- `@Transactional` 放在合适的公开服务边界，理解传播、回滚和代理限制。
- Spring Security 中分别验证认证、角色/权限和资源归属。
- 配置通过现有 profile 与配置类管理；修改密钥、环境变量和迁移前先确认。
- 统一异常映射，外部响应不泄漏堆栈和数据库细节。
- 测试按范围选择单元测试、slice test 或集成测试，避免所有测试都启动完整上下文。
