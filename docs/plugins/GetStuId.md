# GetStuId

## 简介
从指定群拉取成员列表，提取 QQ 与学号映射并写入数据库。

## 基本信息
- 插件名：`GetStuId`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`GetStuId <群号>`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- 仅 `owner_id` 可用

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 拉取指定群的成员列表
- 通过群名片前缀提取学号
- 把学号与 QQ 的映射写入 `stu_qq_id_map`

## 外部依赖
- PostgreSQL
- 需要 OneBot 侧支持 `get_group_member_list`

## 注意事项
- 只会记录群名片中包含 `学号-...` 格式的成员

## 相关代码
- `plugins/GetStuId/GetStuId.py`
