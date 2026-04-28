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
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 从当前群名片中提取学号
- 按群号查找写死的学期编号
- 联表查询 `linecounts` 和 `stu_qq_id_map`
- 校验学号对应 QQ 是否与当前用户一致，再返回统计结果

## 外部依赖
- PostgreSQL

## 注意事项
- 群号到学期编号、总人数映射写死在代码中
- 群名片格式不符合预期时不会查询

## 相关代码
- `plugins/LineCount/LineCount.py`
