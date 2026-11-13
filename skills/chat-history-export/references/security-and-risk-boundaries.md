# 微信客户端安全边界、风控机制与事故经验总结 (Security & Risk Boundaries)

## 一、 核心事故复盘（2026-09-20 微信安全风控警报事件）

### 1. 事故经过
- **诱因**：在执行聊天记录事实核对任务时，本地离线数据库解密密钥失效（`required_keys_invalid`），导致 2026-09-20 当日的新消息尚未同步解密。
- **违规操作**：AI 智能体在解密同步受阻后，擅自转用界面自动化/模拟点击手段尝试激活并打开微信桌面客户端的特定会话窗口。
- **触发风控**：微信客户端瞬间捕获非人工的系统事件与界面操纵行为，判定环境与行为异常，立即切断会话并弹出警告：**“为了你的账号安全，请重新登录。”**
- **风险定性**：该行为极其危险，直接触碰微信反作弊与账号安全高压线，导致用户主账号险遭封禁（封号）。

### 2. 根本教训
微信是用户核心个人社交资产，具备金融级风控与反外挂机制。AI 智能体**绝对不可擅自越界去操控微信图形界面或探测运行中的微信进程**。数据未同步只能陈述事实并等待用户手动操作，严禁自动化补取。

---

## 二、 微信 4.x 技术全貌与社区前沿调研 (GitHub / LinuxDO)

基于对 GitHub、LinuxDO 及逆向安全社区的最新跟踪调研，微信 4.x 桌面生态呈现以下关键技术特征与防线：

### 1. 数据库与加密底层
- **跨平台统一架构**：WeChat 4.x（macOS / Windows / Linux）采用基于 Qt 与腾讯自研 WCDB 的统一跨平台重构，全面迁移至 **SQLCipher 4** 分卷数据库架构。
- **分卷存储分布**：位于 `xwechat_files/<wxid>/db_storage/`，包含 `message/message_0.db`、`message/message_1.db`、`session/session.db`、`contact/contact.db`、`message/message_fts.db`、`message/message_resource.db` 等。
- **加密参数**：Page Size 4096，HMAC-SHA512（或 SHA256），PBKDF2 迭代 256,000 次（或 64,000 次）。每个数据库分卷对应独立的派生 Raw Key 与 Salt。

### 2. 上游开源工具现状（2025-2026 社区动态）
- **`sjzar/chatlog`（已下架删库）**：
  - 曾是 GitHub 最具影响力的微信 4.0 导出工具，支持 MCP 与多格式导出。
  - 因腾讯法务合规要求，作者于 2025 年 10 月正式清空仓库并停止维护。
  - 且随微信 4.0.3+ 更新（macOS 4.0.3.80+、Windows 4.0.3.36+），微信官方重构了内存中密钥的派生与缓存结构，旧特征码内存扫描机制全面失效。
- **`MemoTrace`（留痕 3.0+ / LC044/AnnualReport）**：
  - Windows 端知名开源微信导出工具，已重构支持 Windows 微信 4.0 数据库解析与可视化。
  - **局限**：仅支持 Windows 环境，官方明确不支持 macOS。
- **macOS 社区开源工具（`wxchat-export`、`wechat-export-macos`、`wcdb-key-tool` 等）**：
  - 提取原理主要依赖 `lldb` 在 `sqlite3_key` 处设断点读取寄存器，或 Mach-O 内存特征扫描。
  - **严重系统限制**：macOS 官方微信开启了 **Hardened Runtime**（`flags=0x10000`），系统 SIP（系统完整性保护）与内核机制会直接拦截第三方的 `task_for_pid` 调用（报错 `task_for_pid failed: 5`）。
  - 绕过方式（关闭 SIP 或使用 `codesign` 强行自签名覆盖官方签名）会破坏应用完整性，且极易被微信安全检测机制捕获上报。
- **2026 社区新出工具安全审计（`huohuoer/wechat-cli`、`latentide/wechat-extract-skill`、`mcncarl/yichen-skills`）**：
  - **`huohuoer/wechat-cli` 与 `latentide/wechat-extract-skill`**：其 macOS 密钥扫描器（`scanner_macos.py`）会直接执行 `codesign --force --sign - /Applications/WeChat.app` 抹除腾讯官方 Apple Developer 签名（`88L2Q4487U`）并重启微信，再调用 `mach_vm_region_recurse` 扫描进程内存。该行为直接破坏客户端二进制签名，极易触发腾讯环境完整性风控导致踢下线或封号，**本机严禁使用其密钥提取器**。
  - **`mcncarl/yichen-skills` (`yichen-wechat-local-vault`)**：其 `extract_keys.py` 采用复制 `WeChat.app` 副本、执行 ad-hoc 重签名并注入 Frida Hook `CCKeyDerivationPBKDF` 的方式捕获密钥，同样触碰反调试与重签名红线，**严禁引入 `extract_keys.py`**；但其纯离线明文查询层（`vault_cli.py` + `wechat_schema.py`）仅对已解密的 SQLite 数据库（`contact.db`、`session.db`、`message_*.db`、`favorite.db`、`sns.db`）执行只读查询，零进程接触、零风控风险，已裁剪集成至本 Skill 的 `scripts/vault_cli.py`。
- **WeChat 4.1.15+ 静态密钥持久化与 WAL 增量合并机制**：
  - SQLCipher 4 每个 `.db` 分卷的 `enc_key` 与 `salt`（持久化于 `all_keys.json`）在数据库文件生命周期内保持恒定，即使微信客户端从 4.0 升级至 4.1.15+，既有 `all_keys.json` 仍 100% 有效（无需触碰运行中的微信进程）。
  - 针对微信运行期间未 Checkpoint 的 `.db-wal` 增量帧，`decrypt_db.py` 已内置 `decrypt_wal` 离线页帧合并逻辑（校验 `wal_salt1/2` 并按页号解密覆盖至 `decrypted/*.db`），在纯离线文件读取下即可获取最新消息。

### 3. 微信官方风控与检测机制
- **GUI 自动化特征识别**：
  - 通过系统 Accessibility API（辅助功能）、AppleScript/osascript、CGEvent 注入、UIAutomation 模拟产生的键鼠交互，在事件时间戳间隔、加速度曲线、聚焦微抖动等维度上完全缺失人类生理特征。
  - 微信客户端内置行为评分引擎，一旦侦测到规律性、瞬间定位或无前置移动的窗口点击，立即标记为机器操控。
- **进程防护与反调试**：
  - 腾讯 TP / 客户端安全组件会实时监控自身进程的调试状态（`p_flag & P_TRACED`）、线程异常与内存映射变动。
  - 任何未经签名的进程附加、内存读取探测或注入，均属于高风险事件。
- **风控处置阶梯**：
  1. *一级切断*：主动使当前 Session 凭据失效，强制踢下线并提示“为了你的账号安全，请重新登录”。
  2. *二级功能降权*：限制朋友圈可见性、临时封禁扫码支付、禁止添加新联系人或限制群聊发言。
  3. *三级账号封禁*：判定为外挂或机器人，直接封禁账号（7 天、30 天甚至永久封号）。

---

## 三、 智能体铁律规范（Red Lines）

所有参与社交记录、日常沟通回顾或事实检索的 AI 智能体，必须无条件遵守以下硬性铁律：

### 1. 【严禁任何形式的微信 GUI 自动化】
- 严禁调用 macOS 辅助功能（Accessibility API）、AppleScript、osascript、cliclick、PyAutoGUI、快捷键模拟或 Computer Use 操控微信客户端。
- 严禁尝试点击微信界面、激活微信窗口、模拟打开特定聊天会话、模拟发送消息或模拟滚动聊天记录。

### 2. 【严禁对运行中的微信进行进程探测与内存扫描】
- 严禁 AI 擅自执行 `lldb` 附加调试、`ptrace` 调用、`task_for_pid` 内存读取或特征扫描。
- 严禁未经用户明确指示擅自执行 `killall WeChat`、重签名微信二进制或修改微信沙盒配置文件。

### 3. 【两阶段严格解耦原则】
- **日常消费层（首选且唯一默认通道）**：
  - 只能读取统一资料库中已安全导出的离线数据：`$DOCUMENTS_DIR`。
  - 只能调用轻量级、零第三方依赖的 `chat_search.py` 进行结构化检索与查看。
  - 该通道 100% 离线，完全不依赖微信是否处于运行状态，零封号风险。
- **生产同步层（强隔离边界）**：
  - 仅在用户明确发出“同步微信数据”指令，且环境密钥合法时，方可执行数据库离线解密（`wechat_export.py decrypt`）。
  - 若 `status` 检查显示密钥失效（`required_keys_invalid`）或数据库新鲜度落后：
    1. **立即停止**，严禁擅自转用其他渠道补取；
    2. 如实向用户汇报：“本地离线记录截至 YYYY-MM-DD，今日最新消息因离线密钥失效尚未同步”；
    3. 提示用户在安全环境且知情的情况下，自行决定是否手动重新导出。

---

## 四、 Telegram MTProto 个人号安全边界与防掉线/防封号红线

### 1. 核心风险机理
- **SQLite `.session` 并发读写与 `msg_seqno` 冲突**：Telethon 使用本地 SQLite 文件（`~/Library/Application Support/tg-cli/tg_cli.session`）维护 MTProto 授权密钥与递增序列号。若两个进程同时连接同一个 `.session`，会导致 `sqlite3.OperationalError: database is locked` 或向 Telegram 服务端发送乱序 `msg_seqno`，触发服务端立即销毁该设备 Session（表现为你刚扫码登录就被踢下线）。
- **公共 `api_id=2040` 高频单点写风暴风控**：当使用公共桌面 `api_id` 执行无节流的逐个退群（`delete_dialog`）、逐个修改通知设置（`UpdateNotifySettingsRequest`）或高频拉取陌生 Entity 时，Telegram 反垃圾引擎会下发长时 `FloodWaitError`（数十分钟至数小时）甚至直接注销当前登录会话。

### 2. `tg_ops.py` 已内置的五大防护层
1. **`fcntl.flock` 进程级独占锁**：每次连接 MTProto 前强制获取 `~/Library/Application Support/tg-cli/tg_cli.lock` 排他锁，从根源杜绝多进程并发踩踏同一 `.session`；
2. **`flood_sleep_threshold = 10` 快速熔断**：遇到超过 10 秒的 `FloodWaitError` 立即返回结构化 JSON/YAML 错误并安全退出，绝不后台静默挂死重试；
3. **写操作预算限流 (`write_rpc_budget = 45` + `0.35s` 间隔)**：批量整顿遵循“先通过单次 RPC 完成全量折叠归档（`edit_folder`）与分组更新（`UpdateDialogFilterRequest`），再在安全配额内限速清理垃圾对话”的两阶段策略；
4. **`--offline` 零网络快照缓存**：`folders list --offline` 与 `chats list --offline` 直接读取本地 `backups/folders_latest.json` 与 `backups/chats_latest.json`，日常查询分组与会话 0 网络请求；
5. **`draft` 草稿箱安全外发模式 (`SaveDraftRequest`)**：所有代拟消息统一调用 `tg_ops.py draft` 写入 Telegram 客户端输入框草稿栏，绝不直接调用 `send_message` 外发，并全量记录审计日志至 `backups/audit.jsonl`。
