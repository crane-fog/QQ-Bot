# QiuDao

## 简介
根据数据库中的课程成绩记录返回对应表情的插件。

## 基本信息
- 插件名：`QiuDao`
- 类型：`Group`
- 作者：`just monika / Heai`
- 文档由AI生成：`是`

## 触发方式
- `Theresa 求刀`
- `Theresa 公开我的期末成绩吧`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- 无额外权限限制

## 配置项
- 无插件专属 `self.config` 配置项

## 执行逻辑
- 从群名片中提取学号
- 按群号查学期编号，并联表查询成绩和 QQ 映射
- QQ 与学号映射不一致时拒绝查询
- 根据成绩转换为不同数量的刀表情或花表情

## 外部依赖
- PostgreSQL

## 注意事项
- `Theresa 求刀` 的旧调用词只在部分群可用
- 群号到学期编号映射写死在代码里

## 相关代码
- `plugins/QiuDao/QiuDao.py`
