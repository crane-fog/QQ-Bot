# TheresaHelp

## 简介
列出当前群已启用插件及其说明的基础帮助插件，适合做最小联通性验证。

## 基本信息
- 插件名：`TheresaHelp`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- `Theresa help`
- `Theresa help <插件名>`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 不带参数时，遍历当前群实际生效的插件并输出介绍
- 带插件名时，只返回该插件在当前群的说明或未启用提示

## 外部依赖
- 无

## 注意事项
- 只能显示当前已经成功加载且当前群启用的插件

## 相关代码
- `plugins/TheresaHelp/TheresaHelp.py`
