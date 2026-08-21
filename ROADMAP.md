# QQ-Bot Roadmap

## 初始化配置

- LLBot 与主程序的 systemd 参考配置
- 部分插件额外依赖 PostgreSQL、Redis、LLM API Key、语音 API 等
- 考虑 k8s 部署支持

## 插件文档

- 插件触发词
- 插件配置项解释
- 插件对外部的额外依赖（moegoe api？）

## 其他

- **Gitea Webhook 支持**
- 重写 WebController，目前弃用
- 为 Api 引入 TypedDict
- 小特完整 agent 流程（记忆）
- bot 名称加入触发词
