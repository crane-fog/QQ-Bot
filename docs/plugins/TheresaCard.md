# TheresaCard

## 简介
用于检查高程课程群名片格式、校验选课名单，并可选踢人或输出调试信息。

## 基本信息
- 插件名：`TheresaCard`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`Theresa card (kick/debug) (strict) (unenter) (<小时数>)`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- 普通检查要求 `permission_ids`、群管理员/群主或助教权限
- `kick` 仅 `permission_ids` 和 `owner_id` 可用

## 配置项
- `ignored_ids`：检查时忽略的用户 QQ 列表
- `permission_ids`：允许执行检查/踢人的用户列表

## 执行逻辑
- 解析 `kick`、`debug`、`strict`、`unenter` 和时间限制参数
- 拉取群成员列表并做基础名片格式校验
- `strict` 分支会查数据库校验是否在选课名单中
- `unenter` 分支会查数据库找出已选课但未入群的成员
- 可按参数决定是否踢出不符合要求的成员

## 外部依赖
- PostgreSQL

## 注意事项
- 群号和学期/班级映射写死在代码里
- 功能面向特定课程群，迁移到其他场景前需要改代码

## 相关代码
- `plugins/TheresaCard/TheresaCard.py`
