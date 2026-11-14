# Android 协议逆向、跨框架解包与高并发执行规范 (`android-reverse-engineering.md`)

## 1. 静态反编译与三源社区经验先行

动手脱壳或还原复杂签名前：
1. 同步检索 **GitHub**（`developer-resource-search` / `gh`）、**LinuxDO**（`linuxdo`）与**吾爱破解 `52pojie.cn`**（`reach_hub.py 52pojie rss` 或 `anysearch site:52pojie.cn <包名/特征>` 定位帖子 URL -> `reach_hub.py 52pojie read <url>` 经 `:9223` 静默读取并自动 `/cleanup`，严禁高频扫站触发瑞数 WAF）。
2. 调用 `adb_ops.py top-app` 只读定位前台包名、Activity 与 APK 路径（`pm path`），按产物指纹选择工具（调用前先 `command -v <tool>` 探测是否已安装，禁止盲目重装或建临时 `venv`）：

| 产物特征 / 框架指纹 | 逆向与还原工具路由 | 核心提取目标 |
| :--- | :--- | :--- |
| **标准 Android DEX (`classes*.dex`)** | `jadx` | `Application`、OkHttp `Interceptor`、`Retrofit` 注解、签名头（`sign`/`x-hmac`/`nonce`）及 `System.loadLibrary` JNI 入口 |
| **Flutter AOT (`libflutter.so` + `libapp.so`)** | `blutter` + `reFlutter` | 对 `arm64-v8a/libapp.so` 运行 `blutter` 提取 `pp.txt` Dart 常量池与伪汇编（不在空壳 `FlutterActivity` DEX 里盲搜 URL） |
| **React Native Hermes (`index.android.bundle` 魔数 `\xc6\x1f\xbc\x03`)** | `hermes-dec` (`hbc-decompiler`) | `head -c 4` 区分明文 Metro JS 与预编译 HBC 字节码，反编译还原路由与签名拼串 |
| **原生二进制 (`ELF .so` / `Mach-O`)** | `Ghidra` (`analyzeHeadless`) / `radare2` / `rizin` | 查 `JNI_OnLoad`、`RegisterNatives` 动态绑定表与 `.rodata` 密码学常量（AES S-Box / SHA256 IV），定位偏移后再用 Frida 验证 |
| **Electron 桌面壳 (`resources/app.asar`)** | `npx --yes @electron/asar extract app.asar ./unpacked` | 直接审计 `main.js`、`preload.js` IPC 与渲染层源码 |

## 2. 小米 8 沙箱动态验证与纯协议执行器规范

- **Frida 仅作算法对拍**：在小米 8 Root 沙箱启动 `frida-server` Hook 签名入参与返回值，交叉验证纯 Python/Go 还原实现，不把 Frida RPC 留在高并发生产热路径上。
- **`--preflight` + `[REQ_TRACE]` 审计日志**：协议执行脚本须提供 `--preflight`（核验服务器 NTP 时钟偏移、Token 有效性与代理连通性），并在执行期输出毫秒级 `[REQ_TRACE]`（本地时间戳、协程标识、HTTP 状态码、业务码与 `latency_ms`）。

## 3. 自研移动端/软路由控制台 UI 规范

- 对标 `chen08209/FlClash`、`Mygod/VPNHotspot`、`MetaCubeX/metacubexd` 等成熟开源实现；
- 采用分段导航 + Bento 卡片 + `VectorDrawable`/`Canvas` 矢量图形，禁止用 `[切换]`、`↓` 纯文本充当按钮；
- 每次装包后必跑 `adb_ops.py screencap --out /tmp/adb_screen.jpg`（`<120 KB`）调 `read_file` 目检，确认无省略号截断与底部导航栏遮挡。
