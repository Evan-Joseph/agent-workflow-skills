# 微信 4.x、QQ (NapCat/QCE) 与 Telegram (`tg` / `tg_ops.py`) 完整 CLI 速查手册

## 1. 微信明文 SQLite Vault 全量检索（`vault_cli.py`）

解释器：`python3`（`wechat-export` 运行时）

```bash
PY_WX=python3
VAULT=$HOME/.agents/skills/chat-history-export/scripts/vault_cli.py

# 状态与实时滞后分钟数检测（支持 --sync-if-stale 纯离线增量刷新）
$PY_WX $VAULT status

# 离线只读联系人盘点（无备注好友、现有标签分布、重名与共同群聊上下文）
$PY_WX $VAULT contacts-audit
$PY_WX $VAULT contacts-audit --json

# 最近会话 / 未读会话 / 全库搜索 / 指定会话完整时间线
$PY_WX $VAULT recent --limit 20 --format text --sync-if-stale
$PY_WX $VAULT unread --format text
$PY_WX $VAULT search "关键词" --limit 20 --format text
$PY_WX $VAULT history "会话名或wxid" --limit 50 --format text

# 文件传输助手 (filehelper) + 收藏夹个人笔记与灵感提取
$PY_WX $VAULT notes --since 2026-11-01 --limit 30 --format text --sync-if-stale
$PY_WX $VAULT notes --since 2026-11-01 --save-aliases --format text
$PY_WX $VAULT notes --tag res --tagged-only --format text
$PY_WX $VAULT notes --semantic-query "大模型评测与Agent工作流" --limit 10 --format text
$PY_WX $VAULT notes --since 2026-11-01 --llm --format text

# 收藏夹、朋友圈、群成员、发言统计与群聊摘要素材包
$PY_WX $VAULT favorites --limit 20 --format text
$PY_WX $VAULT moments --name "联系人名称" --keyword "关键词" --format text
$PY_WX $VAULT members "群聊名称" --format text
$PY_WX $VAULT stats "会话名或群名" --format text
$PY_WX $VAULT digest-source "群聊名称" --start 2026-10-01
$PY_WX $VAULT sync-aliases
```

## 2. 微信 4.x 离线增量解密与导出（`wechat_export.py`）

解释器：`python3`（`homebrew-stdlib` 运行时；仅在用户明确指示同步且密钥有效时运行）

```bash
# 检查数据库新鲜度与密钥状态（full_disk_access_required 代表宿主缺少 FDA 权限；required_keys_invalid 代表密钥过期需用户手动刷新，严禁触碰微信 GUI 或进程内存）
python3 $HOME/.agents/skills/chat-history-export/scripts/wechat_export.py status

# 一键增量解密并导出至 ~/Documents/微信聊天记录资料库/exports/
python3 $HOME/.agents/skills/chat-history-export/scripts/wechat_export.py sync

# 分步执行（按需）
python3 $HOME/.agents/skills/chat-history-export/scripts/wechat_export.py decrypt
python3 $HOME/.agents/skills/chat-history-export/scripts/wechat_export.py export-targets -i
python3 $HOME/.agents/skills/chat-history-export/scripts/wechat_export.py summarize-exports
```

## 3. QQ 历史导出与备注/分组受控写回（`napcat_api.py`）

解释器：`python3`（对接本地 NapCat `:3000` / QCE `:40653`）

```bash
NAP=$HOME/.agents/skills/chat-history-export/scripts/napcat_api.py

# QCE 连通性与历史导出
python3 $NAP qce-health
python3 $NAP qce-messages-export \
  --peer-uid <群号或好友UID> --chat-type group --format JSON \
  --output-dir "$DOCUMENTS_DIR" --use-friendly-file-name

# 只读好友与分组盘点
python3 $NAP contacts-audit --format markdown

# 修改备注或分组（默认仅打印 dry-run 预览，获用户确认后附 --confirm 落盘）
python3 $NAP set-friend-remark --user-id <QQ号> --remark "<语境化备注>" --confirm
python3 $NAP set-friend-category --user-id <QQ号> --category-id <分组ID> --confirm
```

## 4. Telegram 离线检索与分组治理（`tg` & `tg_ops.py`）

解释器：`python3`（`tg-cli-runtime`）

```bash
PY_TG=python3
TG_OPS=$HOME/.agents/skills/chat-history-export/scripts/tg_ops.py

# 零网络离线查看分组与活跃会话（首选）
$PY_TG $TG_OPS folders list --offline
$PY_TG $TG_OPS chats list --offline --active-only

# 本地 SQLite 消息极速查询
tg search "关键词" -n 20
tg top
tg context <chat_id> <msg_id>

# 在线登录态、群聊摘要素材包与草稿起草（严禁绕过 draft 直接代发消息）
$PY_TG $TG_OPS status
$PY_TG $TG_OPS digest "群聊名称" --hours 72 --limit 200
$PY_TG $TG_OPS draft "会话名称或@username" "拟回复草稿内容"

# 受控分组更新与会话归档（内置 fcntl.flock 锁与 0.35s 限流预算）
$PY_TG $TG_OPS folders update "分组名" --add-chats "@channel"
$PY_TG $TG_OPS chats archive "群名或ID"
```
