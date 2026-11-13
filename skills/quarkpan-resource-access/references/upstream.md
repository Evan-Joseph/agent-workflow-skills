# 上游与本机适配记录

核验日期：2026-10-22

## 本机运行真相源

- QR 可执行文件：`quarkpan-qr`（`QuarkPan CLI v1.0.8`）
- 兼容 Rust 下载器：`quarkpan`
- 源码仓库：`https://github.com/deepinfan/quarkpan-cli`
- 本机源码：`$HOME/.local/src/quarkpan-cli`
- 本机 HEAD：`4dad033`（2026-05-17）
- GitHub `deepinfan/quarkpan-cli` 当前 `main` 仍为 `4dad033`，没有比本机 `v0.1.0` 更新的提交或发布版本（核验日期：2026-10-22）。
- `ihmily/QuarkPanTool` 最新 release 为 `v0.0.6`（2025-12-18）；release 说明仅称修复“小于 100M”的限速，
  没有改变大文件直链协议或提供 macOS Agent 可调用的官方接口。
- `AlistGo/alist` 当前 `drivers/quark_uc` 是可工作的主要参考：使用 `drive.quark.cn`、桌面客户端
  User-Agent、最小 `pr/fr` 参数，并通过 Range 分段下载。其实现还会接收和刷新 `__puus`。
- `lich0821/QuarkPan` Issue #5 的 2026-07 讨论确认普通 Web API 对大文件返回 `23018`，用户通过
  AList + WebDAV 成功下载大文件，为本次回溯提供了上游线索。
- QR 适配源码：`$HOME/.local/src/quarkpan-skill`
- QR 适配上游：`https://github.com/woshihoujinxin/quarkpan-skill`（已同步至上游 `v1.0.8` / `290ae5b8bda73fda6fe0d53d65cc37725389617d`，并保留本机 Range/`__puus` 大文件下载与 `~/.config/quarkpan/cookie` 只读兼容补丁）
- 已确认命令：`auth qr --no-open`、`auth wait`、`auth login --method api`、`auth status`、`ls`、`download`、`save`、`info`

### 2026-10-22 上游 `v1.0.8` 融合升级要点
1. **非阻塞两步扫码（`auth qr` + `auth wait`）**：吸收上游出码与等扫码分离机制及纯 Python 零依赖 PNG 编码器（`quark_client/utils/qr_png.py`），Agent 可先非阻塞生成二维码展示给用户，再调用 `auth wait` 轮询并自动落盘凭证。
2. **非交互终端防挂死契约**：吸收 `cli/utils.py` 的 `is_interactive()` / `confirm_action()`，非交互终端下若未显式传入 `-f` 立即以退出码 `2` 快速失败，杜绝 `Confirm.ask` 永久阻塞。
3. **文件详情接口防张冠李戴契约**：吸收 `services/file_service.py` 的 `GET file/info?fid=` 精确匹配契约，移除未命中时回退返回根目录第一条文件的危险兜底。

本机 Rust CLI 使用 `QUARK_COOKIE` 环境变量，支持按远程路径或 `fid:` 下载，并对大文件
使用 Range 断点续传。它不是 MCP Server，也没有通用 Agent schema，因此本 Skill 负责流程
和门禁，Harness 继续调用这个唯一 CLI。

认证入口：本机新增 `quarkpan-qr auth login`，来自已核验的 Python 上游，生成
`~/.quarkpan/config/qr_code.png` 并轮询扫码状态；登录状态由上游写入其私有配置目录。
Agent 只呈现二维码和读取非敏感登录状态，不读取、回显或复制 Cookie。

## 对比过的候选

- `OpenMinis/MinisSkills/quark-hub`：偏 iSH/Hermes，硬编码 `/var/minis/skills` 和
  `minis-browser-use`，不适合作为本机 Codex 真源。
- `woshihoujinxin/quarkpan-skill`：功能覆盖更广，含扫码登录、上传、删除、转存等，
  但会探测多个客户端 Cookie 目录并提供高副作用命令；未直接安装，避免产生第二套认证
  owner。
- `DavidBB-L/cinema-manager`：面向影视搜索、转存和媒体库整理，不是通用网盘资源 Skill；
  不纳入 Harness。

这些仓库只作为实现对比，不复制 Cookie、配置、浏览器登录态或第三方 Skill 文件。

## 大文件限制核验（2026-08-15）

- `ihmily/QuarkPanTool` [Issue #16](https://github.com/ihmily/QuarkPanTool/issues/16) 的复现日志
  显示旧 Web API 对大于 100 MB 的文件返回 `download file size limit`。
- [Issue #28](https://github.com/ihmily/QuarkPanTool/issues/28) 中维护者明确说明这是夸克官方 Web
  端限制，即使 SVIP 也可能触发；维护者随后指向 `v0.0.5`，通过桌面客户端请求参数获取大文件直链。
  这证明了“Web 取直链限制”真实存在，但不证明每个签名 CDN URL 都可被第三方下载器消费。
- 本机 2026-08-15 复现并修正了两个阶段：普通 Web UA 返回 `23018`；错误的整套 Cookie 或丢失
  新 `__puus` 会使 CDN 返回 `412`。正确链路是桌面 UA 取直链、接收新 `__puus`、仅携带该 Cookie
  做 Range 下载。
- `103.10 MiB` MP4 已完整下载并通过字节数、ffprobe 和 SHA-256 验收，证明大文件链路恢复。
- 7 月 PDF 下载记录明确采用“分享内容定点转存到个人盘，再用 Python `FileDownloadService`
  下载”的路线；临时脚本已清理，当前只能确认该路线与本次视频的 Web API 失败阶段不同，不能据此
  声称所有大文件都应当成功。
