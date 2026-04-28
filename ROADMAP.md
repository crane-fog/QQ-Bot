# QQ-Bot Roadmap

## 初始化配置

- 数据库建表脚本（需求统一的数据 models）
- LLBot 与主程序的 systemd 参考配置
- 部分插件额外依赖 PostgreSQL、Redis、LLM API Key、语音 API 等

## 插件文档

- 插件触发词
- 插件配置项解释
- 插件对外部的额外依赖

## 其他

- **Gitea Webhook 支持**
- 重写 WebController，目前弃用
- config toml
- 为 Api 引入 TypedDict

## 未来

- LLBot Hook QQ 资源占用大，考虑更换 Napcat 以减少资源占用
