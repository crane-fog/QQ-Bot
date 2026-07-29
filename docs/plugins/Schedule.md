# Schedule

## 简介
查看群友今日课表状态的插件，汇总每个已导入课表的群友当前状态（正在上课/下一节课/已上完课/今天没课），渲染成图片发回群聊；同时支持通过群文件导入个人课表。

## 基本信息
- 插件名：`Schedule`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- `Schedule`：查询并生成群友课表状态图
- 发送文件名以 `textbook` 开头的群文件（即从 1 系统导出的 `textbook.xls`，消息以 `[CQ:file,file=textbook` 开头）：导入个人课表

## 生效条件
- 需要在 `plugins.toml` 中启用
- 受 `groups.toml` 群启用控制
- 要求 `bot.toml` 中 `database_enable = true`
- 无额外权限限制

## 配置项
- `current_calendar`：当前学期编号，默认为 `121`
- `first_day`：学期第一天日期，格式为 `"YYYY-MM-DD"`，用于计算当前周次

配置示例（`plugins.toml`）：

```toml
[Schedule]
enable = true
current_calendar = 121
first_day = "2026-03-02"
```

## 执行逻辑
- 收到课表文件时下载并用 xlrd 解析课程序号列，按学号新旧两种格式存入 `personal_schedule` 表
- 收到 `Schedule` 命令时根据 `first_day` 计算当前周次，联查 `courses` 表取出每个群友当天的课程时间块
- 按当前时间判断每人状态（正在上课/下一节课/已上完课/今天没课）及剩余时间
- 用 Jinja2 模板 `template.j2` 渲染 HTML，再用 Playwright 无头浏览器截图后发回群聊

## 外部依赖
- PostgreSQL（`courses`、`personal_schedule` 表）
- Playwright（可选依赖，通过 `uv sync --extra Schedule` 安装，仅本插件需要）
- `requests`、`xlrd`、`jinja2`
- `GetData.py`：每学期一次性运行的数据采集脚本，需自行登录 1 系统获取 `sessionid` 填入后运行，把课程数据写入 `courses` 表

## 注意事项
- 查询功能依赖 `GetData.py` 预先导入的学期课程数据，未导入时所有人都显示"今天没课"
- 课表导入只识别从 1 系统"个人课表-查看教材"导出的 `textbook.xls` 文件
- 运行目录下需要有 `temp/textbook` 和 `temp/pic` 目录存放临时文件

## 相关代码
- `plugins/Schedule/Schedule.py`
- `plugins/Schedule/GetData.py`
- `plugins/Schedule/template.j2`
