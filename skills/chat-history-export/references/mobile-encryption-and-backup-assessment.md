# Android WeChat Legacy Encryption Parameters & Official LAN Backup SOP

## 1. Technical Cross-Verification of Android `EnMicroMsg.db`

Cross-referenced against open-source mobile forensics frameworks (`abrignoni/ALEAPP`, `EnMicroMsg.db-Password-Cracker`):

- **Database Location**: `/data/data/com.tencent.mm/MicroMsg/<md5("mm" + uin)>/EnMicroMsg.db`
- **Legacy SQLCipher Parameters** (distinct from desktop WeChat 4.x SQLCipher 4 `4096B page + 256,000 iter`):
  - `PRAGMA key = '<7-char lowercase hex>';`
  - `PRAGMA cipher_use_hmac = OFF;`
  - `PRAGMA cipher_page_size = 1024;`
  - `PRAGMA kdf_iter = 4000;`
- **Key Derivation**: `lowercase(MD5(IMEI || str(uin))[0:7])`, where `_auth_uin` is stored in `shared_prefs/auth_info_key_prefs.xml`. On Android 10+ (API 29+), unprivileged apps cannot read hardware IMEI and fall back to the constant `"1234567890ABCDEF"`.

### Critical Operational Boundaries
1. **Non-Root Devices Cannot Pull `/data/data/com.tencent.mm/`**:
   - `android:allowBackup="false"` disables `adb backup`; `Shizuku` (`shell` UID `2000`) is blocked by SELinux `untrusted_app` isolation.
   - **Never log a primary personal IM account onto a rooted secondary phone solely to extract databases** — cross-device login onto rooted environments triggers high-severity risk control.
2. **Desktop Backup Bundles (`xwechat_files/Backup/`) Use Session Keys**:
   - Official encrypted backup bundles (`BAK_0_TEXT` / `Backup.db`) negotiate session-scoped symmetric keys and cannot be opened with the 7-character formula above.

---

## 2. Recommended Zero-Risk Disaster-Recovery SOP (Official LAN Migration)

To preserve historical mobile messages on unrooted flagship phones without breaking hardware attestation (Knox / StrongBox) or triggering anti-cheat flags:

1. Connect both the mobile phone and desktop computer to the same local Wi-Fi / LAN segment with desktop WeChat signed in;
2. On the mobile WeChat client, navigate to **Me -> Settings -> Chats -> Chat History Migration & Backup -> Migrate -> Migrate to Computer WeChat**, and select the target conversations;
3. Once official LAN migration merges historical messages (deduplicated by `server_id`) into the desktop database, run your offline indexing workflow to refresh read-only search snapshots;
4. Optionally run **Backup & Restore -> Back Up Chat History to Computer** onto an encrypted external drive for cold storage.
