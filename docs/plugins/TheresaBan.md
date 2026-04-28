# TheresaBan

## 简介
群禁言插件，允许符合权限条件的用户对指定成员执行禁言。

## 基本信息
- 插件名：`TheresaBan`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`Theresa ban <@> <禁言秒数>`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 不要求数据库
- 仅 bot 主人、群管理员/群主、助教可用

## 配置项
- `black_list`：禁止在这些群里使用禁言插件
  说明：代码实际读取该配置，但当前 `configs/plugins.ini.template` 未提供这一项

## 执行逻辑
- 解析被 `@` 的目标 QQ 和禁言秒数
- 校验当前用户权限以及群是否在黑名单中
- 对普通成员执行禁言
- 如果目标是 `owner_id`，改为反手禁言操作者

## 外部依赖
- 无

## 注意事项
- 依赖消息中 `@` 的 CQ 码格式正确
- 配置模板未声明 `black_list`，启用前需要手动补到 `plugins.ini`

## 相关代码
- `plugins/TheresaBan/TheresaBan.py`
