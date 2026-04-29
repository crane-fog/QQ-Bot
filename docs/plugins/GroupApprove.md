# GroupApprove

## 简介
自动处理入群申请的插件，支持格式检查、学号检查和严格名单校验。

## 基本信息
- 插件名：`GroupApprove`
- 类型：`GroupRequest`
- 作者：`kiriko / Heai`
- 文档由AI生成：`是`

## 触发方式
- 群请求事件触发

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- 助教会被直接放行

## 配置项
- `parts`：申请答案拆分段数
- `reject`：格式或学号不合法时是否直接拒绝
- `strict`：是否按数据库名单严格校验

## 执行逻辑
- 只处理 `sub_type == "add"` 的入群申请
- 从申请答案中提取学号信息并做格式检查
- 非严格模式按学号范围判断，严格模式查数据库名单
- 根据结果批准、拒绝或挂起申请

## 外部依赖
- PostgreSQL

## 注意事项
- 群号到学期的映射写死在代码里
- 严格模式依赖数据库中已有 `stulists` 数据
- 代码默认入群问题文本中包含 `\\n答案：` 这一分隔形式，监听端或题目格式变化时可能直接出错

## 相关代码
- `plugins/GroupApprove/GroupApprove.py`
