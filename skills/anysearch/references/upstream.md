# 上游说明

- 上游仓库：https://github.com/anysearch-ai/anysearch-skill
- 导入版本：`v2.1.0`；已选择性吸收至 `v3.1.0` 的 Python CLI 改进。
- 导入提交：`6ff6aa958ad9747659d669b5e9984f07c896f2aa`
- 许可证：Apache-2.0，完整文本见 `../LICENSE`
- 本地入口：`scripts/anysearch_cli.py`

## 本地补丁

- 仅保留 macOS 需要的 Python 入口，删除重复的 Node、PowerShell 和 Bash 实现。
- 不把 AnySearch 设为所有搜索的默认工具。
- 增加本机专用 Skill 优先级和敏感查询禁用规则。
- 禁止自动注册账号、自动创建或自动持久化 Key。
- Key 不存入 Skill 目录；改从进程环境或 `~/.config/anysearch/anysearch.env` 读取。
- 按正式隐私政策记录查询摘要和日志保留风险。
- 已吸收 v3.0.1 的宽容垂直参数解析、批量查询共享参数和 `finance.quote` 示例，以及 v3.1.0 的 REST 端点、`--tag / --params / --zone / --language`、部分失败的并发批量查询和带 request ID 的错误输出；不采用其“默认所有搜索均使用 AnySearch”、Skill 内 `.env` 写 Key 或自动注册/持久化凭据的建议。

更新时先比较上游 Release 和 Python CLI，再手工重放本地补丁。不要整目录覆盖。
