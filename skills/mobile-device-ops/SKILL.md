---
name: mobile-device-ops
description: "Android ADB multi-device fleet governance, <120KB auto-downsampled screenshot inspection, UI hierarchy XML dumping, safe system debloat redlines, read-only SMS OTP extraction, and mobile reverse-engineering triage."
metadata:
  short-description: Android ADB fleet ops, compact screenshots, safe debloat & RE triage
---

# Mobile Device Operations & Android Reverse Engineering (`mobile-device-ops`)

Standardizes multi-device Android ADB operations, low-overhead visual inspection, safe package debloating, read-only OTP retrieval, and static-first reverse engineering.

## Runtime Contract & Quick Commands

`scripts/adb_ops.py` uses Python 3 (with optional `Pillow` or macOS `sips` fallback for automatic JPEG downsampling):

```bash
# 1. Inspect connected USB / wireless ADB devices (model, Android version, battery, resolution)
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py devices

# 2. Downsampled screenshot (enforces long edge <= 1280px JPEG, < 120KB to prevent multimodal context bloat)
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py screencap --out /tmp/adb_screen.jpg

# 3. Dump lightweight UI Accessibility XML tree & bounds without image overhead
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py ui-dump --out /tmp/window_dump.xml

# 4. Audit installed system / third-party packages and battery/thermal health
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py packages --filter launcher
python3 $HOME/.agents/skills/mobile-device-ops/scripts/adb_ops.py battery-perf
```

---

## 1. Anti-Bloat Screenshot & Headless Inspection Gate

- **Root Problem**: Raw `adb exec-out screencap -p` PNGs from flagship phones/tablets are `2.5 MB–4.5 MB` each. Feeding raw screenshots into multimodal agent contexts bloats session databases and triggers payload limits.
- **Mandatory Rules**:
  1. Always capture via `adb_ops.py screencap --out /tmp/adb_screen.jpg` (`<= 1280px`, JPEG quality `80`, `40–100 KB`) before visual inspection;
  2. Prefer `adb_ops.py ui-dump` when checking text presence or tap coordinates;
  3. Avoid third-party mirroring MCP servers that force-enable `AccessibilityService` on banking/production phones or steal desktop window focus;
  4. Remove `/tmp/adb_screen*.jpg` temporary artifacts when finished.

---

## 2. Android System Debloat Safety Redlines

1. **Reversible User-Space Disable Only — Never Modify `/system`**:
   ```bash
   # Preferred reversible disable
   adb shell pm disable-user --user 0 <package_name>

   # Instant restore
   adb shell pm enable <package_name>
   adb shell cmd package install-existing <package_name>
   ```
2. **Third-Party Launcher Gesture Preservation**:
   - On OEM ROMs (One UI / HyperOS / ZUI), set the new launcher as Default Home *before* freezing OEM promotional services, and never uninstall the stock launcher package (`com.*.launcher`) because system recents and gesture navigation depend on its signature.
3. **Never-Disable System Packages (Bootloop & Companion-Wipe Prevention)**:
   - **`com.android.sdksandbox` (Android 13+)**: `PackageManagerService` asserts an enabled SDK sandbox at boot; disabling triggers `RuntimeException: There should exactly one sdk sandbox package; found 0` and forces `RescueParty` recovery mode;
   - **Wearable Companion Plugins (`com.samsung.wearable.*`, `com.google.android.wearable.app.*`)**: Running `pm uninstall` without `-k` wipes `companiondevice` pairing keys and forces a factory reset on paired smartwatches;
   - **OEM OAID / Device-ID Providers (e.g., `com.zui.deviceidservice`)**: Disabling causes immediate `NullPointerException` crashes in apps linked against MSA OAID SDKs;
   - **Core Infrastructure**: `com.google.android.webview`, package installer, permission controller, OTA updater, Bluetooth/IMS telephony services, and user-installed production apps without explicit confirmation.

---

## 3. Read-Only SMS OTP Extraction

When an automated login flow triggers an SMS verification code on an authorized USB/LAN debugging device, extract it read-only instead of asking the user to copy it manually:

```bash
adb -s "${ADB_SERIAL}" shell "content query --uri content://sms/inbox --projection date:address:body --sort 'date DESC'" | head -n 5
```

---

## 4. Mobile App Reverse-Engineering Triage Matrix

Before attaching dynamic instrumentation (`frida-server`), identify the application packaging stack and route to the matching static analyzer:

| Target Artifact / Magic Signature | Primary Static Tooling | Key Extraction Targets |
| :--- | :--- | :--- |
| **Standard Dalvik/ART (`classes*.dex`)** | `jadx` / `apktool` | `OkHttp` interceptors, `Retrofit` interfaces, custom signing headers (`sign`, `x-hmac`, `nonce`), JNI `System.loadLibrary` entrypoints |
| **Flutter AOT (`libflutter.so` + `libapp.so`)** | `worawit/blutter` + `reFlutter` | Recover Dart class/function symbols and `ObjectPool` string/API constants before socket traffic interception |
| **React Native Hermes (`index.android.bundle`, magic `\xc6\x1f\xbc\x03`)** | `P1sec/hermes-dec` (`hbc-decompiler`) | Decompile Hermes bytecode (`HBC`) to readable pseudo-JS and inspect API client modules |
| **Unity IL2CPP (`libil2cpp.so` + `global-metadata.dat`)** | `Il2CppDumper` / `Cpp2IL` | Reconstruct C# method offsets and metadata headers for targeted native hooks |
| **Native JNI (`.so` ELF arm64)** | `Ghidra` / `radare2` + `Frida` | Verify pure-Python re-implementations against hooked native input/output pairs; keep heavy `Frida` RPC out of high-concurrency production loops |

### Protocol Executor Reliability Standard
- Emit structured `[REQ_TRACE]` logs (millisecond timestamp, worker ID, HTTP status, business return code, end-to-end `latency_ms`);
- Provide a `--preflight` check validating NTP clock skew, token freshness, and network reachability before entering time-critical request loops.
