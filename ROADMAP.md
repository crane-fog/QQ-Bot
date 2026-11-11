# QQ-Bot Roadmap

## 初始化配置

- LLBot 与主程序的 systemd 参考
- 考虑 k8s 部署支持

## 插件文档

- 插件触发词
- 插件配置项解释
- 插件对外部的额外依赖（Schedule 的 playwright）

## 其他

- **Gitea Webhook 支持**
- WebController：TOML 配置管理与 Compose 配置编辑已支持，不访问 Docker daemon；后续考虑 LLBot 配置联动，容器启停保持在宿主机
- 为 Api 引入 TypedDict
- 小特完整 agent 流程（记忆）
- bot 名称加入触发词
- 实现 reload / 文件监听热重载能力
