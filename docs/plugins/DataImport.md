# DataImport

## 简介
把本地文本数据导入数据库的管理插件，用于成绩、行数和学生名单数据初始化。

## 基本信息
- 插件名：`DataImport`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`DataImport scores/linecounts/stulists/stulists_detail <学期课程编号>`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- 仅 `owner_id` 可用

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 解析目标表名和学期编号
- 从插件目录下的 `data/<table_name>/<semester>.txt` 读取文本数据
- 按表类型构造待写入数据
- 先删除同学期旧数据，再批量插入新数据

## 外部依赖
- PostgreSQL
- 本地数据目录：`plugins/DataImport/data/`

## 注意事项
- 数据文件不存在会直接报错
- 这是高权限管理插件，不适合普通群成员使用

## 相关代码
- `plugins/DataImport/DataImport.py`
