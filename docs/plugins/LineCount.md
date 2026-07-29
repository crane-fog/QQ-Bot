# LineCount

## 简介
查询课程作业网代码行数统计的插件。

## 基本信息
- 插件名：`LineCount`
- 类型：`Group`
- 作者：`just monika / Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`Theresa linecount`

## 生效条件
- 需要在 `plugins.toml` 中启用
- 受 `groups.toml` 群启用控制
- 要求 `bot.toml` 中 `database_enable = true`
- 无额外权限限制

## 配置项
在 `plugins.toml` 的 `[LineCount]` 段下配置：
- `semesters`：群号到学期编号的映射，如 `[LineCount.semesters]` 中 `"12345" = 252610`
- `total_people`：学期编号到总人数的映射，如 `[LineCount.total_people]` 中 `"252610" = 1111`

配置示例：

```toml
[LineCount]
enable = false

[LineCount.semesters]
"12345" = 252610
"67890" = 252620

[LineCount.total_people]
"252610" = 1111
"252620" = 2222
```

## 执行逻辑
- 从当前群名片中提取学号
- 按群号从配置中查找学期编号
- 联表查询 `linecounts` 和 `stu_qq_id_map`
- 校验学号对应 QQ 是否与当前用户一致，再返回统计结果

## 外部依赖
- PostgreSQL

## 注意事项
- 群号到学期编号、学期到总人数的映射需在 `plugins.toml` 中配置
- 群名片格式不符合预期时不会查询

## 相关代码
- `plugins/LineCount/LineCount.py`
