---
name: quarkpan-resource-access
description: "用于夸克网盘（Quark Cloud Drive）分享链接核查、个人网盘文件检索、分享元数据只读读取及受批资源大文件 Range 断点续传下载（统一通过本机受管 CLI quarkpan-qr 执行）。"
metadata:
  short-description: 夸克网盘资源检索、分享元数据读取与下载
---

# Quark 网盘资源接入

本 Skill 是 Harness 的网盘资源入口，默认使用本机 QR 入口：
`quarkpan-qr`。原 Rust 下载器
`quarkpan` 保留作兼容回退。扫码登录由 Agent 启动命令并呈现
二维码，用户只需用夸克 App 扫码；不复制 Cookie，不把影视搜索器当成通用网盘接口。

## 路由

- 夸克分享链接、夸克文件浏览、夸克资源下载：使用本 Skill。
- 百度、阿里云盘、115、OneDrive 等其他平台：先检查是否有对应官方 CLI/MCP；不要把
  夸克命令猜测套用到其他平台。
- 需要打开用户登录态网页：遵守 `browser-routing`，不能为取 Cookie 创建临时 Profile。
- 需要解析 PDF、压缩包或 Office 文件：下载后再按文件类型调用对应解析 Skill。

## 最小流程

1. 首先检查现有 CLI 登录态，只有确认失效时才生成二维码：

   ```bash
   quarkpan-qr auth status
   ```

   该状态命令必须用网盘根目录只读请求在线验证 Cookie；只看到 Cookie 字段、本地文件或
   “已登录”缓存不算成功。网络失败或服务端拒绝时报告“登录状态无法验证/登录已失效”，
   不得擅自生成二维码。Python 适配器只读兼容既有 `~/.config/quarkpan/cookie`，不得因为
   不存在 `cookies.json` 就创建第二个认证 owner。确认确需登录后，优先使用 `v1.0.8`
   非阻塞两步扫码入口（避免后台进程长阻塞）：

   ```bash
   # 第一步：非阻塞生成二维码 PNG 并落盘待扫码 token
   quarkpan-qr auth qr --no-open
   ```

   命令会立即返回并输出 `QR_PNG_PATH=<绝对路径>` 与 `QR_TOKEN=<token>`。Agent 读取
   `QR_PNG_PATH` 将二维码呈现给用户，待用户用夸克 App 扫码后执行第二步：

   ```bash
   # 第二步：等待扫码完成并自动兑换/落盘 cookies.json
   quarkpan-qr auth wait
   ```

   （兼容单步阻塞入口：`quarkpan-qr auth login --method api`。）
   同一登录会话存活时禁止重复生成第二张二维码。只允许 `qr`/`wait` 或 `--method api`；
   `auto` 模式会在 API 扫码失败后降级到手动 Cookie 输入，禁止用于 Agent 扫码流程。
   二维码约 5 分钟失效；过期或 API 失败后进程直接退出。先确认旧进程已经结束并
   报告原因，得到用户明确同意后才能重试。登录完成后验证：

   ```bash
   quarkpan-qr auth status
   ```

   只有该在线只读验证成功才能报告登录完成。登录 Cookie 只由客户端写入其私有配置目录；
   Agent 绝不索取、读取、回显、复制或写入 Cookie。用户已有 CLI 登录态优先复用，不迁移、不另存。
2. **只读递归预检分享目录树（统计文件总数与总字节数）**，确认资源用途、预计大小、落盘绝对路径和是否允许下载。面对多层级分享文件夹时，必须在转存或下载前先只读遍历分享树汇总真实总体积（路径必须在当前工作区或用户明确指定的目录内；**单文件超过 `300 MiB` 或整棵分享树预计新增超过 `1 GiB`，必须先停下向用户汇报预检摘要并获确认**）：

   ```bash
   # 只读递归统计夸克分享链接的文件总数、总字节数（MiB/GiB）与扩展名分布（零写入、零 Cookie 回显）
   $HOME/.local/src/quarkpan-skill/.venv/bin/python -c '
   import collections, json, os, sys
   from quark_client import QuarkClient
   url = sys.argv[1]
   client = QuarkClient()
   share_id, pwd = client.shares.parse_share_url(url)
   stoken = client.shares.get_share_token(share_id, pwd)
   files, dirs, total_bytes, exts = 0, 0, 0, collections.Counter()
   stack = ["0"]
   while stack:
       pdir = stack.pop()
       page = 1
       while True:
           resp = client.api_client.get(
               "share/sharepage/detail",
               params={"pwd_id": share_id, "stoken": stoken, "pdir_fid": pdir, "force": "0", "_page": page, "_size": 100, "_fetch_total": "1"},
               base_url=client.config.SHARE_BASE_URL,
           )
           items = (resp.get("data") or {}).get("list") or []
           for it in items:
               if it.get("dir") or it.get("file_type") == 0:
                   dirs += 1
                   stack.append(str(it["fid"]))
               else:
                   files += 1
                   total_bytes += int(it.get("size") or 0)
                   exts[os.path.splitext(it.get("file_name") or "")[1].lower() or "<noext>"] += 1
           if len(items) < 100:
               break
           page += 1
   print(json.dumps({"share_id": share_id, "dirs": dirs, "files": files, "total_bytes": total_bytes, "total_mib": round(total_bytes / 1048576, 2), "total_gib": round(total_bytes / 1073741824, 3), "over_1gib_gate": total_bytes >= 1073741824, "top_exts": dict(exts.most_common(8))}, ensure_ascii=False, indent=2))
   ' 'https://pan.quark.cn/s/<id>?pwd=<提取码>'
   ```
3. 分享链接先查看帮助并确认命令支持范围：

   ```bash
   quarkpan-qr --help
   quarkpan-qr save 'https://pan.quark.cn/s/<id>?pwd=<提取码>' --help
   ```

   `save`/`batch-save` 会把分享内容转存到用户自己的夸克盘，这是外部写入，必须在执行
   前单独说明并得到用户确认。不能把“浏览分享”说成已经转存或下载。
4. 受批准下载使用明确输出路径，并在完成后核验文件存在、大小和 SHA-256；断点续传时
   先检查已有文件，禁止覆盖不明来源的同名文件。
5. 记录来源 URL（必要时脱敏提取码）、文件名、大小、SHA-256、下载时间和许可/用途；
   不保存 Cookie、Token、密码或个人网盘目录快照。

## 大文件与 CDN 限制

- 夸克 Web 下载接口存在约 `100 MiB` 的单文件取直链限制；服务端常返回 HTTP 400、错误码
  `23018`、`download file size limit`。这不是本 Skill 的 `300 MiB` 用户确认门槛。大文件必须走
  `quarkpan-qr download`，不要使用旧 Rust `quarkpan` 回退。
- 大文件直链请求使用 `https://drive.quark.cn/1/clouddrive/file/download`，仅带
  `pr=ucpro&fr=pc` 和 AList 已验证的夸克桌面客户端 User-Agent。不得改用 `drive-pc`，不得附加
  `sys/ve/ut/guid/__t/__dt`，否则服务端可能重新返回 `23018`。
- 取直链请求携带登录 Cookie，响应会刷新 `Set-Cookie: __puus`。后续 CDN Range 请求只能携带
  这个刚刷新的 `__puus`，不能携带旧的完整账号 Cookie；完整 Cookie、丢失新 `__puus` 或普通
  全量 GET 都可能返回 `412 Precondition Failed`。
- CDN 必须按 Range 分段下载，当前最小实现使用不小于 8 MiB 的分片、`.part` 临时文件和原子替换。
  中断后从 `.part` 当前大小继续；完成前不得把 `.part` 或 0 字节目标文件称为下载成功。
- 2026-08-15 已完成实际大文件验收：`2-1 线性表的顺序存储.mp4`，远端与本地均为
  `108,106,483` 字节（103.10 MiB），H.264/AAC、1440×1080、2478.45 秒，SHA-256
  `824d0a152b3c380db1e2f9f7b7be7ec13eabbd8327112f14182783b3c4c19da1`。
  因此本机大文件下载能力已经恢复；仍须逐文件遵守容量确认、完整性和媒体格式验收。

## 写操作门禁

现有 `quarkpan` 是下载器，未来若接入支持上传、转存、删除、重命名或移动的上游 CLI，
这些命令均属于外部副作用：执行前说明目标、影响和可回滚方式，逐次确认；默认只读。
转存分享前先列分享内容，再列目标目录，检查同名项，避免重复转存。

## 收尾检查

- [ ] 实际使用的 CLI 路径和命令已记录。
- [ ] 目标文件存在，大小与 SHA-256 已回读。
- [ ] 没有覆盖不明同名文件，没有遗留临时 Profile 或 Cookie 副本；扫码登录生成的临时二维码图片（如 `/tmp/quarkpan_qr*.png`）已在登录成功后当回合清理。
- [ ] 下载失败时保留失败状态，不把部分文件称为完成；必要时删除不完整临时产物前先确认。
- [ ] 若后续需要解析，交给对应文件解析 Skill，并保留原始文件为 canonical。

上游实现和适配边界见 `references/upstream.md`。
