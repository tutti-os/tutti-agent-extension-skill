# Tutti Agent Extension Skill

这是一个用于设计、实现、发布和排查 Tutti 第三方 Agent Extension 的可复用
Skill。

Skill 总结了 Gemini CLI 接入过程中验证过的完整方法，但所有核心流程保持
provider 无关，覆盖：

- 评审 Agent Extension 的信任边界与模块归属；
- 创建独立 Extension 仓库；
- 声明 Runtime 探测、能力、工具、模型和权限语义；
- 在 Tutti 中接入开放 provider identity 和固定 Agent Target；
- 标准化 ACP 模型、事件、错误和 lifecycle snapshot；
- 使用 Tutti 可复用工作流构建可重复、带签名的发布产物；
- 上传 S3/CloudFront，并排查 catalog、安装、composer 和会话问题。

## 安装

```sh
npx --yes skills add tutti-os/tutti-agent-extension-skill
```

本地验证：

```sh
python3 scripts/validate_repository.py
```

本仓库描述的是连接 Tutti 与外部 ACP Runtime 的声明式扩展包，不实现或重新
分发 Agent Runtime 本身。
