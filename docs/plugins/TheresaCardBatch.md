# TheresaCardBatch

## 简介
批量调用 `TheresaCard`，对多个目标群执行同样的群名片检查逻辑。

## 基本信息
- 插件名：`TheresaCardBatch`
- 类型：`Group`
- 作者：`Heai`
- 文档由AI生成：`是`

## 触发方式
- 触发命令：`Theresa card ...`
- 实际上复用了 `TheresaCard` 的同一触发词，并把当前事件转交给 `TheresaCard.main(...)`

## 生效条件
- 需要在 `plugins.ini` 中启用
- 受 `groups.ini` 群启用控制
- 要求 `database_enable = True`
- 依赖 `TheresaCard` 已成功加载

## 配置项
- `target_groups`：要批量检查的群号列表

## 执行逻辑
- 从 `bot.plugins_list` 中找到 `TheresaCard`
- 暂时改写事件中的 `group_id`
- 按 `target_groups` 逐群调用 `TheresaCard.main(...)`
- 调用完成后恢复原始群号

## 外部依赖
- PostgreSQL
- 依赖 `TheresaCard` 插件实例

## 注意事项
- 如果 `TheresaCard` 未加载，这个插件不会真正执行检查
- 它不是独立的批量命令体系，而是借用 `TheresaCard` 的参数和权限逻辑
- 由于两者使用同一触发词，启用时需要留意是否会与 `TheresaCard` 本体形成重复执行

## 相关代码
- `plugins/TheresaCardBatch/TheresaCardBatch.py`
