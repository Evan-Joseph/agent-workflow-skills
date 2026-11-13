#!/usr/bin/env python3
"""
Unified read-only query CLI for the decrypted wechat-local-vault.

Mac commands read the local decrypted vault produced by decrypt_all_dbs.py.
The explicit snapshot subcommand uses a separately validated plaintext snapshot.
It does not touch the WeChat UI, send messages, or modify WeChat databases.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import urllib.error
import urllib.request
from xml.etree import ElementTree as ET

from wechat_schema import message_columns as shared_message_columns
from wechat_schema import message_table as shared_message_table

try:
    import zstandard as zstd
except Exception:  # pragma: no cover - optional runtime dependency
    zstd = None


CONFIG_FILE = Path(os.environ.get("WECHAT_VAULT_CONFIG", "~/.local/share/wechat-vault/config.json")).expanduser()
DEFAULT_VAULT_DIR = Path(os.environ.get("WECHAT_VAULT_DIR", "~/.local/share/wechat-vault")).expanduser()
DEFAULT_DECRYPTED_DIR = Path(os.environ.get("WECHAT_DECRYPTED_DIR", str(DEFAULT_VAULT_DIR / "decrypted"))).expanduser()
DEFAULT_EXPORTS_DIR = Path("~/Documents/微信聊天记录资料库/exports").expanduser()
STATE_FILE = DEFAULT_VAULT_DIR / "state/vault_cli_last_check.json"
ALIAS_STATE_FILE = DEFAULT_VAULT_DIR / "state/chat_aliases.json"
TAG_ALIAS_STATE_FILE = DEFAULT_VAULT_DIR / "state/note_tag_aliases.json"
MAGPIE_VAULT_KEY_FILE = Path("~/.agents/config/magpie-wechat-vault.json").expanduser()
MAGPIE_PROBE_KEY_FILE = Path("~/.agents/config/magpie-ops-probe.json").expanduser()
DEFAULT_RERANK_MODEL = "moark/Qwen3-Reranker-4B"

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
ZSTD_DECODER = zstd.ZstdDecompressor() if zstd else None

MESSAGE_TYPE_FILTERS = {
    "text": (1,),
    "image": (3,),
    "voice": (34,),
    "video": (43,),
    "sticker": (47,),
    "location": (48,),
    "link": (49,),
    "file": (49, 6),
    "call": (50,),
    "system": (10000,),
}

TYPE_LABELS = {
    1: "文本",
    3: "图片",
    34: "语音",
    42: "名片",
    43: "视频",
    47: "表情",
    48: "位置",
    49: "链接/文件",
    50: "通话",
    10000: "系统",
    10002: "撤回",
}

FAVORITE_TYPE_MAP = {
    1: "文本",
    2: "图片",
    5: "文章",
    19: "名片",
    20: "视频号",
}

FAVORITE_TYPE_FILTERS = {
    "text": 1,
    "image": 2,
    "article": 5,
    "card": 19,
    "video": 20,
}


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_config() -> dict:
    return load_json(CONFIG_FILE)


def resolve_decrypted_dir(value: str | None = None) -> Path:
    if value:
        return Path(value).expanduser()
    return DEFAULT_DECRYPTED_DIR


def resolve_exports_dir(value: str | None = None) -> Path:
    config = load_config()
    return Path(value or config.get("exports_dir") or DEFAULT_EXPORTS_DIR).expanduser()


def resolve_db_dir() -> Path | None:
    config = load_config()
    if config.get("db_dir"):
        return Path(config["db_dir"]).expanduser()
    if config.get("db_base_path"):
        return Path(config["db_base_path"]).expanduser()
    if config.get("wxid"):
        return (
            Path("~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files").expanduser()
            / config["wxid"]
            / "db_storage"
        )
    return None


def _safe_mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        return 0.0


def _iso_ts(ts: float) -> str:
    if ts <= 0:
        return ""
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def compute_vault_staleness(
    decrypted_dir: Path,
    db_dir: Path | None = None,
    *,
    threshold_minutes: float = 2.0,
) -> dict:
    """Compare decrypted Vault .db mtimes (ignoring -shm/-wal) against live WeChat db_storage (.db + .db-wal)."""
    live_root = db_dir if db_dir is not None else resolve_db_dir()
    core_relpaths = [
        "message/message_0.db",
        "session/session.db",
        "favorite/favorite.db",
    ]
    for p in message_dbs(decrypted_dir):
        rel = str(p.relative_to(decrypted_dir))
        if rel not in core_relpaths:
            core_relpaths.append(rel)
    if live_root:
        try:
            live_msg_dir = live_root / "message"
            if live_msg_dir.exists():
                for p in sorted(live_msg_dir.glob("*.db")):
                    if re.match(r"^(?:biz_)?message_\d+\.db$", p.name):
                        rel = f"message/{p.name}"
                        if rel not in core_relpaths:
                            core_relpaths.append(rel)
        except OSError:
            pass

    dec_mtimes: list[float] = []
    live_mtimes: list[float] = []
    stale_entries: list[tuple[str, float, float]] = []

    for rel in core_relpaths:
        dec_ts = _safe_mtime(decrypted_dir / rel)
        if dec_ts > 0:
            dec_mtimes.append(dec_ts)
        live_ts = 0.0
        if live_root:
            src = live_root / rel
            wal = Path(f"{src}-wal")
            live_ts = max(_safe_mtime(src), _safe_mtime(wal))
            if live_ts > 0:
                live_mtimes.append(live_ts)
        if live_ts > 0 and (dec_ts <= 0 or live_ts - dec_ts > 5.0):
            stale_entries.append((rel, dec_ts, live_ts))

    latest_dec_ts = max(dec_mtimes) if dec_mtimes else 0.0
    latest_live_ts = max(live_mtimes) if live_mtimes else 0.0

    if stale_entries:
        # Use the newest stale live DB vs the decrypted snapshot mtime among stale DBs
        stale_dec_candidates = [d for _, d, _ in stale_entries if d > 0]
        effective_vault_ts = max(stale_dec_candidates) if stale_dec_candidates else latest_dec_ts
        effective_live_ts = max(l for _, _, l in stale_entries)
        lag_minutes = round(max(0.0, effective_live_ts - effective_vault_ts) / 60.0, 1)
    else:
        effective_vault_ts = latest_dec_ts
        effective_live_ts = latest_live_ts
        lag_minutes = 0.0

    sync_stale = bool(stale_entries and lag_minutes >= threshold_minutes)
    return {
        "vault_synced_at": _iso_ts(effective_vault_ts),
        "live_wechat_updated_at": _iso_ts(effective_live_ts),
        "lag_minutes": lag_minutes if sync_stale else 0.0,
        "sync_stale": sync_stale,
        "stale_databases": [rel for rel, _, _ in stale_entries],
    }


def format_staleness_banner(staleness: dict) -> str:
    if not staleness.get("sync_stale"):
        return ""
    synced_iso = str(staleness.get("vault_synced_at") or "")
    hhmm = "未知时间"
    if synced_iso:
        try:
            dt = datetime.fromisoformat(synced_iso)
            if dt.date() == datetime.now().date():
                hhmm = dt.strftime("%H:%M")
            else:
                hhmm = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            hhmm = synced_iso
    lag = staleness.get("lag_minutes", 0)
    lag_label = int(round(lag)) if float(lag) >= 1 else lag
    return (
        f"[提示: 离线解密库快照停留在 {hhmm}（落后实时微信 {lag_label} 分钟），"
        "如需拉取最新消息请先运行 wechat_export.py sync]"
    )


def maybe_sync_if_stale(args: argparse.Namespace, decrypted_dir: Path) -> dict:
    """Offline incremental SQLCipher decrypt using cached all_keys.json (strictly zero GUI/LLDB/process touch)."""
    staleness = compute_vault_staleness(decrypted_dir)
    if not getattr(args, "sync_if_stale", False) or not staleness.get("sync_stale"):
        return staleness
    tool_dir = DEFAULT_VAULT_DIR / "wechat-decrypt"
    decrypt_script = tool_dir / "decrypt_db.py"
    cfg = load_config()
    keys_path = tool_dir / (cfg.get("keys_file") or "all_keys.json")
    if not decrypt_script.is_file() or not keys_path.is_file():
        print(
            f"[vault_cli] 无法自动执行离线增量解密（缺少 {decrypt_script} 或缓存密钥 {keys_path}）",
            file=sys.stderr,
        )
        return staleness
    print(
        f"[vault_cli] 检测到离线库落后 {staleness['lag_minutes']} 分钟，正在使用缓存密钥离线增量解密 (decrypt_db.py -i)...",
        file=sys.stderr,
    )
    res = subprocess.run(
        [sys.executable, str(decrypt_script), "-i"],
        cwd=str(tool_dir),
        stdin=subprocess.DEVNULL,
        stdout=sys.stderr,
        stderr=sys.stderr,
        timeout=300,
        check=False,
    )
    if res.returncode != 0:
        print(f"[vault_cli] 离线增量解密返回码 {res.returncode}，继续读取现有明文快照", file=sys.stderr)
    return compute_vault_staleness(decrypted_dir)


def connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    try:
        return {row["name"] for row in con.execute(f"PRAGMA table_info([{table}])")}
    except sqlite3.Error:
        return set()


def table_exists(con: sqlite3.Connection, table: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def safe_name(value: str) -> str:
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value).strip()
    value = re.sub(r"\s+", "_", value)
    return value[:100] or "wechat_export"


def parse_time(value: str | None, *, end_of_day: bool = False) -> int | None:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            if fmt == "%Y-%m-%d" and end_of_day:
                dt = dt.replace(hour=23, minute=59, second=59)
            return int(dt.timestamp())
        except ValueError:
            pass
    raise SystemExit(f"时间格式不支持: {value}")


def split_msg_type(local_type: int | None) -> tuple[int, int]:
    try:
        value = int(local_type or 0)
    except (TypeError, ValueError):
        return 0, 0
    if value > 0xFFFFFFFF:
        return value & 0xFFFFFFFF, value >> 32
    return value, 0


def type_label(local_type: int | None) -> str:
    base_type, _ = split_msg_type(local_type)
    return TYPE_LABELS.get(base_type, f"type={local_type}")


def matches_type(local_type: int | None, filter_name: str | None) -> bool:
    if not filter_name:
        return True
    base_type, sub_type = split_msg_type(local_type)
    expected = MESSAGE_TYPE_FILTERS[filter_name]
    if base_type != expected[0]:
        return False
    return len(expected) == 1 or sub_type == expected[1]


def decode_value(value, compression_flag=None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    data = bytes(value)
    should_try_zstd = data.startswith(ZSTD_MAGIC) or compression_flag == 4
    if should_try_zstd and ZSTD_DECODER:
        try:
            data = ZSTD_DECODER.decompress(data, max_output_size=1_000_000)
        except Exception:
            return "[压缩消息解码失败]"
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return "[二进制内容]"


def output(data, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(data)


def load_contacts(decrypted_dir: Path) -> tuple[dict[str, dict], dict[int, str]]:
    contact_db = decrypted_dir / "contact/contact.db"
    if not contact_db.exists():
        return {}, {}
    alias_data = load_json(ALIAS_STATE_FILE)
    by_user = alias_data.get("by_username") or {}
    contacts: dict[str, dict] = {}
    id_to_username: dict[int, str] = {}
    with connect(contact_db) as con:
        if not table_exists(con, "contact"):
            return {}, {}
        for row in con.execute("SELECT * FROM contact"):
            item = dict(row)
            username = item.get("username") or item.get("userName") or ""
            if not username:
                continue
            username = str(username)
            contact_id = item.get("id")
            if contact_id is not None:
                try:
                    id_to_username[int(contact_id)] = username
                except (TypeError, ValueError):
                    pass
            nick = str(item.get("nick_name") or item.get("nickname") or "")
            remark = str(item.get("remark") or "")
            alias = str(item.get("alias") or "")
            display = remark or nick or alias or username
            prev_names = [
                n for n in (by_user.get(username, {}).get("previous_names") or [])
                if n and n != display and n != nick and n != remark
            ]
            contacts[username] = {
                "username": username,
                "display_name": display,
                "remark": remark,
                "nick_name": nick,
                "alias": alias,
                "previous_names": prev_names,
                "description": str(item.get("description") or ""),
                "avatar": str(item.get("small_head_url") or item.get("big_head_url") or ""),
                "is_group": "@chatroom" in username,
                "is_subscription": username.startswith("gh_"),
                "raw": item,
            }
    for uname, ainfo in by_user.items():
        if uname not in contacts and ainfo.get("previous_names"):
            names = ainfo["previous_names"]
            contacts[uname] = {
                "username": uname,
                "display_name": names[-1],
                "remark": "",
                "nick_name": names[-1],
                "alias": "",
                "previous_names": names[:-1],
                "description": "",
                "avatar": "",
                "is_group": "@chatroom" in uname or uname.startswith("Msg_"),
                "is_subscription": False,
                "raw": {},
            }
    return contacts, id_to_username


def display_name(username: str, contacts: dict[str, dict]) -> str:
    return contacts.get(username, {}).get("display_name") or username


def resolve_chat(query: str, contacts: dict[str, dict]) -> dict | None:
    if query in contacts:
        return contacts[query]
    if query.startswith("wxid_") or "@chatroom" in query or query.startswith("gh_"):
        return {
            "username": query,
            "display_name": contacts.get(query, {}).get("display_name", query),
            "is_group": "@chatroom" in query,
        }
    q = query.lower()
    exact = [
        c for c in contacts.values()
        if q == c["display_name"].lower()
        or q == str(c.get("remark") or "").lower()
        or q == str(c.get("nick_name") or "").lower()
        or any(q == str(pn).lower() for pn in (c.get("previous_names") or []))
    ]
    if exact:
        return exact[0]
    fuzzy = [
        c
        for c in contacts.values()
        if any(q in str(c.get(field) or "").lower() for field in ("display_name", "remark", "nick_name", "alias", "username"))
        or any(q in str(pn).lower() for pn in (c.get("previous_names") or []))
    ]
    return fuzzy[0] if fuzzy else None


def message_dbs(decrypted_dir: Path) -> list[Path]:
    msg_dir = decrypted_dir / "message"
    if not msg_dir.exists():
        return []
    return sorted(
        p for p in msg_dir.glob("*.db")
        if re.match(r"^(?:biz_)?message_\d+\.db$", p.name)
    )


def message_table(username: str) -> str:
    return shared_message_table(username)


def load_name2id(con: sqlite3.Connection) -> dict[int, str]:
    mapping: dict[int, str] = {}
    if not table_exists(con, "Name2Id"):
        return mapping
    try:
        for row in con.execute("SELECT rowid, user_name FROM Name2Id"):
            if row["user_name"]:
                mapping[int(row["rowid"])] = str(row["user_name"])
    except sqlite3.Error:
        return {}
    return mapping


def username_for_table(table: str, con: sqlite3.Connection) -> str:
    if not table.startswith("Msg_"):
        return ""
    target = table[4:]
    if not table_exists(con, "Name2Id"):
        return ""
    try:
        for row in con.execute("SELECT user_name FROM Name2Id"):
            username = str(row["user_name"] or "")
            if hashlib.md5(username.encode()).hexdigest() == target:
                return username
    except sqlite3.Error:
        return ""
    return ""


def username_for_table_from_contacts(table: str, contacts: dict[str, dict]) -> str:
    if not table.startswith("Msg_"):
        return ""
    target = table[4:]
    for username in contacts:
        if hashlib.md5(username.encode()).hexdigest() == target:
            return username
    return ""


def message_columns(con: sqlite3.Connection, table: str) -> dict[str, str]:
    return shared_message_columns(table_columns(con, table), legacy_mac=True)


def build_select_sql(table: str, cols: dict[str, str], start_ts: int | None, end_ts: int | None, keyword: str | None, type_name: str | None, limit: int | None, offset: int = 0) -> tuple[str, list]:
    select_parts = []
    aliases = {
        "local_id": "local_id",
        "server_id": "server_id",
        "local_type": "local_type",
        "create_time": "create_time",
        "real_sender_id": "real_sender_id",
        "message_content": "message_content",
        "compress_content": "compress_content",
        "compression_flag": "compression_flag",
    }
    for key, alias in aliases.items():
        col = cols.get(key)
        if col:
            select_parts.append(f"{col} AS {alias}")
        else:
            select_parts.append(f"NULL AS {alias}")
    clauses = []
    params: list = []
    if start_ts is not None and cols.get("create_time"):
        clauses.append(f"{cols['create_time']} >= ?")
        params.append(start_ts)
    if end_ts is not None and cols.get("create_time"):
        clauses.append(f"{cols['create_time']} <= ?")
        params.append(end_ts)
    if keyword and cols.get("message_content"):
        clauses.append(f"{cols['message_content']} LIKE ?")
        params.append(f"%{keyword}%")
    if type_name and cols.get("local_type"):
        expected = MESSAGE_TYPE_FILTERS[type_name]
        base = expected[0]
        clauses.append(f"({cols['local_type']} & 4294967295) = ?")
        params.append(base)
        if len(expected) > 1:
            sub = expected[1]
            clauses.append(f"(({cols['local_type']} >> 32) & 4294967295) = ?")
            params.append(sub)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"SELECT {', '.join(select_parts)} FROM [{table}] {where} ORDER BY create_time DESC"
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
    return sql, params


def parse_sender_prefix(content: str) -> tuple[str, str]:
    if ":\n" not in content:
        return "", content
    sender, text = content.split(":\n", 1)
    if sender.startswith("wxid_") or "@chatroom" not in sender:
        return sender, text
    return "", content


def media_hint(local_type: int | None, content: str, resolve_media: bool, db_dir: Path | None, chat_username: str, ts: int) -> str | None:
    base_type, _ = split_msg_type(local_type)
    if base_type == 3:
        return "[图片]"
    if base_type == 34:
        match = re.search(r'voicelength="(\d+)"', content or "")
        if match:
            return f"[语音，约 {int(match.group(1)) / 1000:.1f} 秒]"
        return "[语音]"
    if base_type == 43:
        return "[视频]"
    if base_type == 47:
        return "[表情]"
    if base_type == 48:
        return "[位置]"
    if base_type == 42:
        return "[名片]"
    if base_type == 50:
        return "[通话]"
    if base_type != 49 or not resolve_media or not db_dir:
        return None
    title = ""
    try:
        root = ET.fromstring(content)
        title = (root.findtext(".//title") or root.findtext(".//filename") or "").strip()
    except Exception:
        pass
    if not title:
        return None
    file_dir = db_dir.parent / "msg/file"
    if not file_dir.exists():
        return f"[文件] {title}"
    month = datetime.fromtimestamp(ts).strftime("%Y-%m")
    month_dir = file_dir / month
    if month_dir.exists():
        candidate = month_dir / title
        if candidate.exists():
            return f"[文件] {title}\n{candidate}"
    return f"[文件] {title}"


def format_content(local_type: int | None, content: str, resolve_media: bool, db_dir: Path | None, chat_username: str, ts: int) -> str:
    hint = media_hint(local_type, content, resolve_media, db_dir, chat_username, ts)
    if hint:
        return hint
    base_type, sub_type = split_msg_type(local_type)
    if base_type == 49:
        try:
            root = ET.fromstring(content)
            app_type = int(root.findtext(".//type") or 0)
            title = (root.findtext(".//title") or "").strip()
            desc = (root.findtext(".//des") or "").strip()
            if app_type == 57 or sub_type == 57:
                refer = (root.findtext(".//refermsg/content") or "").strip()
                if refer and "<" not in refer:
                    short_ref = re.sub(r"\s+", " ", refer)[:60]
                    return f"{title}\n  ↳ [引用] {short_ref}".strip()
                return title or "[引用消息]"
            if app_type == 5:
                return f"[链接] {title or desc}".strip()
            if app_type in (33, 36, 44):
                return f"[小程序] {title or desc}".strip()
            if sub_type == 6 or app_type == 6:
                return f"[文件] {title or desc}".strip()
            return f"[链接/文件] {title or desc}".strip()
        except Exception:
            return content.strip() or "[链接/文件]"
    if base_type not in (1, 10000):
        return f"[{type_label(local_type)}] {content}".strip()
    return content.strip()


def row_to_message(row: sqlite3.Row, db_name: str, table: str, chat: dict, contacts: dict[str, dict], name2id: dict[int, str], resolve_media: bool = False, db_dir: Path | None = None) -> dict:
    local_type = row["local_type"]
    ts = int(row["create_time"] or 0)
    content = decode_value(row["message_content"], row["compression_flag"]) or decode_value(row["compress_content"], row["compression_flag"])
    prefix_sender, content = parse_sender_prefix(content)
    sender_username = ""
    sender_id = row["real_sender_id"]
    try:
        sender_username = name2id.get(int(sender_id), "")
    except (TypeError, ValueError):
        sender_username = ""
    if not sender_username:
        sender_username = prefix_sender
    if chat.get("is_group"):
        sender = display_name(sender_username, contacts) if sender_username else ""
    elif sender_username and sender_username != chat["username"]:
        sender = display_name(sender_username, contacts)
    elif str(sender_id) == "2":
        sender = "我"
    else:
        sender = chat["display_name"]
    text = format_content(local_type, content, resolve_media, db_dir, chat["username"], ts)
    return {
        "db": db_name,
        "table": table,
        "local_id": row["local_id"],
        "server_id": row["server_id"],
        "type": type_label(local_type),
        "local_type": local_type,
        "sender": sender,
        "sender_username": sender_username,
        "timestamp": ts,
        "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
        "content": text,
    }


def find_chat_tables(decrypted_dir: Path, chat: dict) -> list[tuple[Path, str]]:
    target = message_table(chat["username"])
    matches = []
    for db_path in message_dbs(decrypted_dir):
        with connect(db_path) as con:
            if table_exists(con, target):
                matches.append((db_path, target))
    return matches


def collect_history(decrypted_dir: Path, chat: dict, start_ts: int | None, end_ts: int | None, limit: int, offset: int, type_name: str | None, resolve_media: bool = False) -> list[dict]:
    contacts, _ = load_contacts(decrypted_dir)
    db_dir = resolve_db_dir()
    rows = []
    candidate_limit = limit + offset
    for db_path, table in find_chat_tables(decrypted_dir, chat):
        with connect(db_path) as con:
            cols = message_columns(con, table)
            sql, params = build_select_sql(table, cols, start_ts, end_ts, None, type_name, candidate_limit, 0)
            name2id = load_name2id(con)
            for row in con.execute(sql, params):
                msg = row_to_message(row, db_path.name, table, chat, contacts, name2id, resolve_media, db_dir)
                if matches_type(msg["local_type"], type_name):
                    rows.append(msg)
    rows.sort(key=lambda item: (item["timestamp"], str(item["local_id"])), reverse=True)
    page = rows[offset : offset + limit]
    page.sort(key=lambda item: (item["timestamp"], str(item["local_id"])))
    return page


def command_status(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    staleness = maybe_sync_if_stale(args, decrypted_dir)
    names = [
        "contact/contact.db",
        "session/session.db",
        "sns/sns.db",
        "favorite/favorite.db",
        "message/message_resource.db",
    ]
    names.extend(str(p.relative_to(decrypted_dir)) for p in message_dbs(decrypted_dir))
    data = {
        "decrypted_dir": str(decrypted_dir),
        "exists": decrypted_dir.exists(),
        "vault_synced_at": staleness["vault_synced_at"],
        "live_wechat_updated_at": staleness["live_wechat_updated_at"],
        "lag_minutes": staleness["lag_minutes"],
        "sync_stale": staleness["sync_stale"],
        "stale_databases": staleness["stale_databases"],
        "databases": [{"path": rel, "available": (decrypted_dir / rel).exists()} for rel in sorted(set(names))],
    }
    output(data if args.format == "json" else render_status_text(data, staleness), args.format)


def render_status_text(data: dict, staleness: dict | None = None) -> str:
    lines = []
    if staleness:
        banner = format_staleness_banner(staleness)
        if banner:
            lines.append(banner)
    lines.extend([
        f"明文 vault: {data['decrypted_dir']}",
        f"状态: {'可用' if data['exists'] else '不存在'}",
        f"离线库快照时间: {data.get('vault_synced_at') or '未知'}",
        f"实时微信库时间: {data.get('live_wechat_updated_at') or '未检测'}（滞后 {data.get('lag_minutes', 0)} 分钟）",
        "",
        "数据库:",
    ])
    for item in data["databases"]:
        lines.append(f"  {'OK' if item['available'] else '--'} {item['path']}")
    return "\n".join(lines)


def session_rows(decrypted_dir: Path, only_unread: bool, limit: int | None = None) -> list[dict]:
    session_db = decrypted_dir / "session/session.db"
    if not session_db.exists():
        raise SystemExit(f"找不到 session.db，请先增量或全量解密: {session_db}")
    contacts, _ = load_contacts(decrypted_dir)
    rows = []
    with connect(session_db) as con:
        if not table_exists(con, "SessionTable"):
            raise SystemExit("session.db 中没有 SessionTable")
        where = "WHERE unread_count > 0" if only_unread else "WHERE last_timestamp > 0"
        sql = (
            "SELECT username, unread_count, summary, last_timestamp, last_msg_type, "
            f"last_msg_sender, last_sender_display_name FROM SessionTable {where} "
            "ORDER BY last_timestamp DESC"
        )
        if limit is not None:
            sql += " LIMIT ?"
            query = con.execute(sql, (limit,))
        else:
            query = con.execute(sql)
        for row in query:
            username = str(row["username"] or "")
            summary = decode_value(row["summary"], 4)
            if ":\n" in summary:
                summary = summary.split(":\n", 1)[1]
            sender_username = str(row["last_msg_sender"] or "")
            sender = display_name(sender_username, contacts) if sender_username else str(row["last_sender_display_name"] or "")
            ts = int(row["last_timestamp"] or 0)
            rows.append({
                "chat": display_name(username, contacts),
                "username": username,
                "is_group": "@chatroom" in username,
                "unread": int(row["unread_count"] or 0),
                "last_message": summary,
                "msg_type": type_label(row["last_msg_type"]),
                "sender": sender,
                "timestamp": ts,
                "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
            })
    return rows


def render_sessions_text(rows: list[dict], title: str, staleness: dict | None = None) -> str:
    banner = format_staleness_banner(staleness) if staleness else ""
    if not rows:
        return f"{banner}\n没有找到会话".strip()
    lines = []
    if banner:
        lines.extend([banner, ""])
    lines.extend([f"{title}（{len(rows)} 个）", ""])
    for row in rows:
        head = f"[{row['time']}] {row['chat']}"
        if row["is_group"]:
            head += " [群]"
        if row["unread"]:
            head += f" ({row['unread']}条未读)"
        body = f"  {row['msg_type']}: "
        if row["sender"] and row["is_group"]:
            body += f"{row['sender']}: "
        body += row["last_message"]
        lines.extend([head, body, ""])
    return "\n".join(lines).rstrip()


def command_sessions(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    staleness = maybe_sync_if_stale(args, decrypted_dir)
    rows = session_rows(decrypted_dir, False, args.limit)
    payload = {
        "vault_synced_at": staleness["vault_synced_at"],
        "live_wechat_updated_at": staleness["live_wechat_updated_at"],
        "lag_minutes": staleness["lag_minutes"],
        "sync_stale": staleness["sync_stale"],
        "count": len(rows),
        "sessions": rows,
    }
    output(payload if args.format == "json" else render_sessions_text(rows, "最近会话", staleness), args.format)


def command_unread(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    staleness = maybe_sync_if_stale(args, decrypted_dir)
    rows = session_rows(decrypted_dir, True, args.limit)
    payload = {
        "vault_synced_at": staleness["vault_synced_at"],
        "live_wechat_updated_at": staleness["live_wechat_updated_at"],
        "lag_minutes": staleness["lag_minutes"],
        "sync_stale": staleness["sync_stale"],
        "count": len(rows),
        "sessions": rows,
    }
    output(payload if args.format == "json" else render_sessions_text(rows, "未读会话", staleness), args.format)


def command_new_messages(args: argparse.Namespace) -> None:
    rows = session_rows(resolve_decrypted_dir(args.decrypted_dir), False, None)
    current = {row["username"]: row["timestamp"] for row in rows}
    previous = load_json(STATE_FILE)
    if not previous:
        save_json(STATE_FILE, current)
        unread = [row for row in rows if row["unread"] > 0]
        data = {"first_call": True, "unread_count": len(unread), "messages": unread}
        text = render_sessions_text(unread, "当前未读会话") if unread else "当前无未读消息；已记录状态，下次只返回新增。"
        output(data if args.format == "json" else text, args.format)
        return
    changed = [row for row in rows if row["timestamp"] > int(previous.get(row["username"], 0) or 0)]
    changed.sort(key=lambda item: item["timestamp"])
    save_json(STATE_FILE, current)
    data = {"first_call": False, "new_count": len(changed), "messages": changed}
    text = render_sessions_text(changed, "新增消息") if changed else "无新消息"
    output(data if args.format == "json" else text, args.format)


def command_contacts(args: argparse.Namespace) -> None:
    contacts, _ = load_contacts(resolve_decrypted_dir(args.decrypted_dir))
    if args.detail:
        item = resolve_chat(args.detail, contacts)
        if not item:
            raise SystemExit(f"找不到联系人: {args.detail}")
        data = {k: v for k, v in item.items() if k != "raw"}
        output(data if args.format == "json" else render_contact_detail(data), args.format)
        return
    items = list(contacts.values())
    if args.query:
        q = args.query.lower()
        items = [
            item for item in items
            if any(q in str(item.get(field) or "").lower() for field in ("username", "display_name", "remark", "nick_name", "alias"))
            or any(q in str(pn).lower() for pn in (item.get("previous_names") or []))
        ]
    items.sort(key=lambda item: (not item["is_group"], item["display_name"]))
    items = [{k: v for k, v in item.items() if k != "raw"} for item in items[: args.limit]]
    output({"count": len(items), "contacts": items} if args.format == "json" else render_contacts_text(items), args.format)


def render_contacts_text(items: list[dict]) -> str:
    if not items:
        return "没有找到联系人"
    lines = []
    for index, item in enumerate(items, 1):
        tag = "群" if item["is_group"] else "联系人"
        lines.append(f"{index}. [{tag}] {item['display_name']}")
        if item.get("remark"):
            lines.append(f"   备注: {item['remark']}")
        if item.get("nick_name") and item["nick_name"] != item.get("remark"):
            lines.append(f"   昵称: {item['nick_name']}")
        if item.get("previous_names"):
            lines.append(f"   曾用名: {'、'.join(item['previous_names'][:5])}")
        lines.append(f"   username: {item['username']}")
    return "\n".join(lines)


def render_contact_detail(item: dict) -> str:
    lines = [item["display_name"], f"username: {item['username']}"]
    for key, label in [("remark", "备注"), ("nick_name", "昵称"), ("alias", "微信号"), ("description", "描述"), ("avatar", "头像")]:
        if item.get(key):
            lines.append(f"{label}: {item[key]}")
    if item.get("previous_names"):
        lines.append(f"曾用名: {'、'.join(item['previous_names'])}")
    lines.append(f"类型: {'群聊' if item.get('is_group') else '联系人'}")
    return "\n".join(lines)


SYSTEM_CONTACT_USERNAMES = frozenset({
    "filehelper",
    "weixin",
    "fmessage",
    "medianote",
    "floatbottle",
    "qmessage",
    "notifymessage",
    "tmessage",
    "qqmail",
    "mphelper",
    "brandsessionholder",
    "brandservicesessionholder",
    "newsapp",
    "feedsapp",
    "masssendapp",
    "voipapp",
    "voiceinputapp",
    "linkedinplugin",
})


def connect_readonly(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def _read_varint(buf: bytes, pos: int) -> tuple[int, int] | None:
    val = 0
    shift = 0
    n = len(buf)
    while pos < n:
        b = buf[pos]
        pos += 1
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, pos
        shift += 7
        if shift > 63:
            return None
    return None


def extract_contact_label_ids(extra_buffer: bytes | None, valid_label_ids: set[int]) -> list[int]:
    """Decode WeChat 4.x contact.extra_buffer protobuf field 30 (comma-separated label IDs)."""
    if not extra_buffer:
        return []
    buf = bytes(extra_buffer)
    pos = 0
    n = len(buf)
    found: list[int] = []
    while pos < n:
        tag_res = _read_varint(buf, pos)
        if tag_res is None:
            break
        tag, pos = tag_res
        field_no = tag >> 3
        wire_type = tag & 0x07
        if wire_type == 0:
            v_res = _read_varint(buf, pos)
            if v_res is None:
                break
            _, pos = v_res
        elif wire_type == 1:
            pos += 8
        elif wire_type == 5:
            pos += 4
        elif wire_type == 2:
            ln_res = _read_varint(buf, pos)
            if ln_res is None:
                break
            ln, pos = ln_res
            if ln < 0 or pos + ln > n:
                break
            chunk = buf[pos : pos + ln]
            pos += ln
            if field_no == 30:
                try:
                    raw_str = chunk.decode("utf-8", errors="strict").strip().strip(",")
                except UnicodeDecodeError:
                    continue
                if raw_str:
                    for part in raw_str.split(","):
                        part = part.strip()
                        if part.isdigit():
                            lid = int(part)
                            if (not valid_label_ids or lid in valid_label_ids) and lid not in found:
                                found.append(lid)
        else:
            break
    return found


def _mask_identifier(val: str) -> str:
    if not val:
        return ""
    if val.startswith("wxid_") and len(val) > 10:
        return f"{val[:7]}***{val[-3:]}"
    if len(val) > 6:
        return f"{val[:3]}***{val[-2:]}"
    if len(val) >= 2:
        return f"{val[0]}*"
    return "*"


def _mask_name(val: str) -> str:
    if not val:
        return ""
    s = val.strip()
    if len(s) <= 1:
        return s
    if len(s) == 2:
        return f"{s[0]}*"
    return f"{s[0]}{'*' * min(2, len(s) - 2)}{s[-1]}"


def collect_contacts_audit(
    decrypted_dir: Path,
    *,
    include_openim: bool = False,
    redact: bool = False,
) -> dict:
    contact_db = decrypted_dir / "contact/contact.db"
    if not contact_db.exists():
        alt_contact_db = decrypted_dir / "contact.db"
        if alt_contact_db.exists():
            contact_db = alt_contact_db
        else:
            raise SystemExit(f"找不到明文 contact.db（请先确保已完成离线解密）: {contact_db}")

    chatroom_db_candidates = [
        decrypted_dir / "contact/chatroom.db",
        decrypted_dir / "chatroom/chatroom.db",
        decrypted_dir / "chatroom.db",
    ]
    extra_chatroom_dbs = [p for p in chatroom_db_candidates if p.exists() and p.resolve() != contact_db.resolve()]

    cfg = load_config()
    self_usernames: set[str] = set()
    if cfg.get("wxid"):
        self_usernames.add(str(cfg["wxid"]).strip())
    if cfg.get("db_dir"):
        parent_name = Path(str(cfg["db_dir"])).expanduser().parent.name
        m_self = re.match(r"^(.+)_[0-9a-fA-F]{4}$", parent_name)
        if m_self:
            self_usernames.add(m_self.group(1))
        elif parent_name.startswith("wxid_"):
            self_usernames.add(parent_name)

    labels_by_id: dict[int, dict] = {}
    id_to_username: dict[int, str] = {}
    group_names: dict[str, str] = {}
    raw_friends: list[dict] = []
    openim_count = 0
    total_contact_rows = 0

    with connect_readonly(contact_db) as con:
        if not table_exists(con, "contact"):
            raise SystemExit(f"contact.db 中不存在 contact 表: {contact_db}")

        if table_exists(con, "contact_label"):
            for row in con.execute("SELECT label_id_, label_name_, sort_order_ FROM contact_label ORDER BY sort_order_ ASC, label_id_ ASC"):
                lid = int(row["label_id_"])
                labels_by_id[lid] = {
                    "label_id": lid,
                    "label_name": str(row["label_name_"] or f"label_{lid}"),
                    "sort_order": int(row["sort_order_"] or 0),
                }

        valid_label_ids = set(labels_by_id.keys())
        for row in con.execute("SELECT * FROM contact"):
            total_contact_rows += 1
            item = dict(row)
            username = str(item.get("username") or item.get("userName") or "").strip()
            if not username:
                continue
            cid = item.get("id")
            if cid is not None:
                try:
                    id_to_username[int(cid)] = username
                except (TypeError, ValueError):
                    pass

            nick = str(item.get("nick_name") or item.get("nickname") or "").strip()
            remark = str(item.get("remark") or "").strip()
            alias = str(item.get("alias") or "").strip()
            local_type = int(item.get("local_type") or 0)
            delete_flag = int(item.get("delete_flag") or 0)
            verify_flag = int(item.get("verify_flag") or 0)

            if "@chatroom" in username or local_type == 2:
                group_names[username] = remark or nick or username
                continue

            if delete_flag != 0 or verify_flag != 0:
                continue
            if (
                username.startswith("gh_")
                or username.endswith("@kefu.openim")
                or username in SYSTEM_CONTACT_USERNAMES
                or username in self_usernames
            ):
                continue

            if local_type == 5 or username.endswith("@openim"):
                if local_type == 5:
                    openim_count += 1
                if not (include_openim and local_type == 5):
                    continue
            elif local_type != 1:
                continue

            lids = extract_contact_label_ids(item.get("extra_buffer"), valid_label_ids)
            lnames = [labels_by_id[lid]["label_name"] for lid in lids if lid in labels_by_id]
            display = remark or nick or alias or username
            raw_friends.append({
                "contact_id": int(cid) if cid is not None else None,
                "username": username,
                "alias": alias,
                "nick_name": nick,
                "remark": remark,
                "display_name": display,
                "local_type": local_type,
                "label_ids": lids,
                "labels": lnames,
            })

        # Collect chatroom memberships (room_id -> member_id)
        member_groups: dict[str, set[str]] = {}

        def _ingest_chatroom_tables(db_con: sqlite3.Connection) -> None:
            local_id_map = dict(id_to_username)
            if table_exists(db_con, "contact"):
                for r in db_con.execute("SELECT id, username, remark, nick_name FROM contact"):
                    u = str(r["username"] or "").strip()
                    if r["id"] is not None and u:
                        local_id_map[int(r["id"])] = u
                        if "@chatroom" in u and u not in group_names:
                            group_names[u] = str(r["remark"] or r["nick_name"] or u).strip()
            if table_exists(db_con, "chat_room"):
                cols = table_columns(db_con, "chat_room")
                if {"id", "username"}.issubset(cols):
                    for r in db_con.execute("SELECT id, username FROM chat_room"):
                        u = str(r["username"] or "").strip()
                        if r["id"] is not None and u:
                            local_id_map[int(r["id"])] = u
                            group_names.setdefault(u, u)
            if table_exists(db_con, "chatroom_member"):
                for r in db_con.execute("SELECT room_id, member_id FROM chatroom_member"):
                    rid = r["room_id"]
                    mid = r["member_id"]
                    if rid is None or mid is None:
                        continue
                    room_uname = local_id_map.get(int(rid), f"room_{rid}")
                    mem_uname = local_id_map.get(int(mid), "")
                    if mem_uname:
                        member_groups.setdefault(mem_uname, set()).add(room_uname)

        _ingest_chatroom_tables(con)

    for extra_db in extra_chatroom_dbs:
        with connect_readonly(extra_db) as extra_con:
            _ingest_chatroom_tables(extra_con)

    def _fmt_user(u: str) -> str:
        return _mask_identifier(u) if redact else u

    def _fmt_text(t: str) -> str:
        return _mask_name(t) if redact else t

    # Enrich friends with shared group counts
    friends_enriched: list[dict] = []
    label_stats: dict[int, dict] = {
        lid: {
            "label_id": lid,
            "label_name": info["label_name"],
            "friend_count": 0,
            "unremarked_count": 0,
        }
        for lid, info in labels_by_id.items()
    }
    unlabeled_count = 0
    remark_equals_nick_count = 0

    by_display_key: dict[str, list[dict]] = {}
    for f in raw_friends:
        g_unames = sorted(member_groups.get(f["username"], set()))
        g_titles = [_fmt_text(group_names.get(gu, gu)) for gu in g_unames]
        has_remark = bool(f["remark"])
        if has_remark and f["remark"] == f["nick_name"]:
            remark_equals_nick_count += 1
        if not f["label_ids"]:
            unlabeled_count += 1
        for lid in f["label_ids"]:
            if lid in label_stats:
                label_stats[lid]["friend_count"] += 1
                if not has_remark:
                    label_stats[lid]["unremarked_count"] += 1

        entry = {
            "username": _fmt_user(f["username"]),
            "alias": _fmt_user(f["alias"]) if f["alias"] else "",
            "display_name": _fmt_text(f["display_name"]),
            "remark": _fmt_text(f["remark"]),
            "nick_name": _fmt_text(f["nick_name"]),
            "labels": list(f["labels"]),
            "shared_group_count": len(g_unames),
            "shared_groups": g_titles[:10],
        }
        friends_enriched.append(entry)
        norm_key = f["display_name"].strip().casefold()
        if norm_key:
            by_display_key.setdefault(norm_key, []).append(entry)

    unremarked_friends = [e for e in friends_enriched if not e["remark"]]
    unremarked_friends.sort(key=lambda x: (-x["shared_group_count"], x["display_name"], x["username"]))

    duplicate_names = []
    for norm_key, group in sorted(by_display_key.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        if len(group) >= 2:
            duplicate_names.append({
                "display_name": group[0]["display_name"],
                "count": len(group),
                "contacts": sorted(group, key=lambda x: (-x["shared_group_count"], x["username"])),
            })

    friends_by_groups = sorted(
        [e for e in friends_enriched if e["shared_group_count"] > 0],
        key=lambda x: (-x["shared_group_count"], x["display_name"]),
    )

    label_distribution = sorted(
        label_stats.values(),
        key=lambda x: (-x["friend_count"], x["label_id"]),
    )

    return {
        "source_dbs": {
            "contact_db": str(contact_db),
            "extra_chatroom_dbs": [str(p) for p in extra_chatroom_dbs],
            "read_only": True,
        },
        "summary": {
            "total_contact_table_rows": total_contact_rows,
            "total_friends": len(friends_enriched),
            "openim_contacts_detected": openim_count,
            "include_openim": include_openim,
            "remarked_friends": len(friends_enriched) - len(unremarked_friends),
            "unremarked_friends": len(unremarked_friends),
            "remark_equals_nickname_friends": remark_equals_nick_count,
            "labeled_friends": len(friends_enriched) - unlabeled_count,
            "unlabeled_friends": unlabeled_count,
            "total_labels": len(label_distribution),
            "duplicate_name_groups": len(duplicate_names),
            "total_known_chatrooms": len(group_names),
            "friends_with_shared_groups": len(friends_by_groups),
            "friends_without_shared_groups": len(friends_enriched) - len(friends_by_groups),
            "redacted": redact,
        },
        "label_distribution": label_distribution,
        "unremarked_friends": unremarked_friends,
        "duplicate_names": duplicate_names,
        "top_shared_group_friends": friends_by_groups[:50],
    }


def render_contacts_audit_markdown(audit: dict, limit: int = 50) -> str:
    s = audit["summary"]
    lines = [
        "# 微信联系人离线只读治理审计摘要",
        "",
        f"- 数据源：`{audit['source_dbs']['contact_db']}`（`mode=ro` 纯离线只读）",
        f"- 好友总数：**{s['total_friends']}**（已备注 **{s['remarked_friends']}** / 无备注 **{s['unremarked_friends']}** / 备注与昵称相同 **{s['remark_equals_nickname_friends']}**）",
        f"- 标签覆盖：已打标签 **{s['labeled_friends']}** / 未打标签 **{s['unlabeled_friends']}**（共 **{s['total_labels']}** 个标签；另检测到企业微信/OpenIM 联系人 **{s['openim_contacts_detected']}** 个）",
        f"- 群聊关联：已知群聊 **{s['total_known_chatrooms']}** 个；有共同群聊好友 **{s['friends_with_shared_groups']}** 人 / 零共同群聊好友 **{s['friends_without_shared_groups']}** 人",
        f"- 重名好友组：**{s['duplicate_name_groups']}** 组",
        "",
        "## 1. 标签（`contact_label`）分布",
        "",
        "| 标签 ID | 标签名称 | 好友数 | 其中无备注数 |",
        "| :---: | :--- | :---: | :---: |",
    ]
    for lb in audit["label_distribution"]:
        lines.append(f"| {lb['label_id']} | {lb['label_name']} | {lb['friend_count']} | {lb['unremarked_count']} |")
    lines.append(f"| - | *（未打任何标签）* | {s['unlabeled_friends']} | - |")

    unrem = audit["unremarked_friends"]
    shown_unrem = unrem if limit <= 0 else unrem[:limit]
    lines.extend([
        "",
        f"## 2. 无备注好友名单（共 {len(unrem)} 人，展示前 {len(shown_unrem)} 人）",
        "",
    ])
    if shown_unrem:
        lines.extend([
            "| # | 昵称 | username | 标签 | 共同群聊数 | 代表共同群聊 |",
            "| :---: | :--- | :--- | :--- | :---: | :--- |",
        ])
        for idx, item in enumerate(shown_unrem, 1):
            lbs = "、".join(item["labels"]) if item["labels"] else "-"
            grps = "、".join(item["shared_groups"][:3]) if item["shared_groups"] else "-"
            nick = (item["nick_name"] or item["display_name"]).replace("|", "\\|")
            lines.append(f"| {idx} | {nick} | `{item['username']}` | {lbs} | {item['shared_group_count']} | {grps} |")
    else:
        lines.append("全部好友均已设置备注。")

    dups = audit["duplicate_names"]
    shown_dups = dups if limit <= 0 else dups[:limit]
    lines.extend([
        "",
        f"## 3. 重名好友检测（共 {len(dups)} 组）",
        "",
    ])
    if shown_dups:
        for grp in shown_dups:
            lines.append(f"- **{grp['display_name']}**（{grp['count']} 人）：")
            for c in grp["contacts"]:
                lbs = "、".join(c["labels"]) if c["labels"] else "无标签"
                lines.append(
                    f"  - `{c['username']}` | 昵称: {c['nick_name'] or '-'} | 备注: {c['remark'] or '-'} | 标签: {lbs} | 共同群聊: {c['shared_group_count']}"
                )
    else:
        lines.append("未检测到重名好友。")

    top_sh = audit["top_shared_group_friends"]
    shown_sh = top_sh[: min(15, limit if limit > 0 else 15)]
    lines.extend([
        "",
        f"## 4. 共同群聊数 Top {len(shown_sh)} 好友",
        "",
        "| # | 显示名称 | 备注 | 标签 | 共同群聊数 |",
        "| :---: | :--- | :--- | :--- | :---: |",
    ])
    for idx, item in enumerate(shown_sh, 1):
        lbs = "、".join(item["labels"]) if item["labels"] else "-"
        dname = item["display_name"].replace("|", "\\|")
        rem = (item["remark"] or "-").replace("|", "\\|")
        lines.append(f"| {idx} | {dname} | {rem} | {lbs} | {item['shared_group_count']} |")

    return "\n".join(lines)


def command_contacts_audit(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    fmt = "json" if getattr(args, "as_json", False) else args.format
    audit = collect_contacts_audit(
        decrypted_dir,
        include_openim=bool(getattr(args, "include_openim", False)),
        redact=bool(getattr(args, "redact", False)),
    )
    if fmt == "json":
        output(audit, "json")
    else:
        output(render_contacts_audit_markdown(audit, limit=args.limit), "text")


def command_members(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    contacts, _ = load_contacts(decrypted_dir)
    group = resolve_chat(args.group, contacts)
    if not group or not group.get("is_group"):
        raise SystemExit(f"找不到群聊: {args.group}")
    contact_db = decrypted_dir / "contact/contact.db"
    owner = ""
    members = []
    with connect(contact_db) as con:
        if table_exists(con, "contact") and table_exists(con, "chat_room") and table_exists(con, "chatroom_member"):
            room = con.execute("SELECT id FROM contact WHERE username=? OR userName=?", (group["username"], group["username"])).fetchone()
            if room:
                room_id = room["id"]
                owner_row = con.execute("SELECT owner FROM chat_room WHERE id=?", (room_id,)).fetchone()
                owner_username = str(owner_row["owner"] or "") if owner_row else ""
                owner = display_name(owner_username, contacts) if owner_username else ""
                ids = [row["member_id"] for row in con.execute("SELECT member_id FROM chatroom_member WHERE room_id=?", (room_id,))]
                if ids:
                    placeholders = ",".join("?" for _ in ids)
                    for row in con.execute(f"SELECT id, username, nick_name, remark FROM contact WHERE id IN ({placeholders})", ids):
                        username = str(row["username"] or "")
                        members.append({
                            "username": username,
                            "display_name": row["remark"] or row["nick_name"] or username,
                            "remark": row["remark"] or "",
                            "nick_name": row["nick_name"] or "",
                            "is_owner": username == owner_username,
                        })
    if not members:
        stats = collect_stats(decrypted_dir, group, None, None)
        members = [{"display_name": item["name"], "message_count": item["count"]} for item in stats["top_senders"]]
    members.sort(key=lambda item: (not item.get("is_owner", False), item.get("display_name", "")))
    data = {"group": group["display_name"], "username": group["username"], "owner": owner, "member_count": len(members), "members": members}
    output(data if args.format == "json" else render_members_text(data), args.format)


def render_members_text(data: dict) -> str:
    lines = [f"{data['group']} 群成员（{data['member_count']} 人）"]
    if data.get("owner"):
        lines.append(f"群主: {data['owner']}")
    for index, item in enumerate(data["members"], 1):
        suffix = " [群主]" if item.get("is_owner") else ""
        count = f" - {item['message_count']}条" if "message_count" in item else ""
        lines.append(f"{index}. {item['display_name']}{suffix}{count}")
    return "\n".join(lines)


def command_history(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    staleness = maybe_sync_if_stale(args, decrypted_dir)
    contacts, _ = load_contacts(decrypted_dir)
    chat = resolve_chat(args.chat, contacts)
    if not chat:
        raise SystemExit(f"找不到聊天对象: {args.chat}")
    rows = collect_history(
        decrypted_dir,
        chat,
        parse_time(args.start_time),
        parse_time(args.end_time, end_of_day=True),
        args.limit,
        args.offset,
        args.type,
        args.media,
    )
    data = {
        "vault_synced_at": staleness["vault_synced_at"],
        "live_wechat_updated_at": staleness["live_wechat_updated_at"],
        "lag_minutes": staleness["lag_minutes"],
        "sync_stale": staleness["sync_stale"],
        "chat": chat["display_name"],
        "username": chat["username"],
        "count": len(rows),
        "messages": rows,
    }
    output(data if args.format == "json" else render_messages_text(rows, staleness), args.format)


def render_messages_text(rows: list[dict], staleness: dict | None = None) -> str:
    banner = format_staleness_banner(staleness) if staleness else ""
    if not rows:
        return f"{banner}\n没有找到消息".strip()
    lines = [banner] if banner else []
    for row in rows:
        sender = f"{row['sender']}: " if row.get("sender") else ""
        lines.append(f"[{row['time']}] {sender}{row['content']}")
    return "\n".join(lines)


def command_search(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    staleness = maybe_sync_if_stale(args, decrypted_dir)
    contacts, _ = load_contacts(decrypted_dir)
    start_ts = parse_time(args.start_time)
    end_ts = parse_time(args.end_time, end_of_day=True)
    candidate_limit = args.limit + args.offset
    results = []
    chats = []
    if args.chat:
        for chat_query in args.chat:
            chat = resolve_chat(chat_query, contacts)
            if chat:
                chats.append(chat)
        for chat in chats:
            for row in collect_history(decrypted_dir, chat, start_ts, end_ts, candidate_limit, 0, args.type, False):
                if args.keyword.lower() in row["content"].lower():
                    row["chat"] = chat["display_name"]
                    row["chat_username"] = chat["username"]
                    results.append(row)
    else:
        for db_path in message_dbs(decrypted_dir):
            with connect(db_path) as con:
                tables = [row["name"] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")]
                name2id = load_name2id(con)
                for table in tables:
                    username = username_for_table(table, con) or username_for_table_from_contacts(table, contacts)
                    chat = {
                        "username": username,
                        "display_name": display_name(username, contacts) if username else table,
                        "is_group": "@chatroom" in username,
                    }
                    cols = message_columns(con, table)
                    sql, params = build_select_sql(table, cols, start_ts, end_ts, args.keyword, args.type, candidate_limit, 0)
                    try:
                        for row in con.execute(sql, params):
                            msg = row_to_message(row, db_path.name, table, chat, contacts, name2id)
                            if args.keyword.lower() in msg["content"].lower() and matches_type(msg["local_type"], args.type):
                                msg["chat"] = chat["display_name"]
                                msg["chat_username"] = chat["username"]
                                results.append(msg)
                    except sqlite3.Error:
                        continue
    results.sort(key=lambda item: item["timestamp"], reverse=True)
    page = results[args.offset : args.offset + args.limit]
    page.sort(key=lambda item: item["timestamp"])
    data = {
        "vault_synced_at": staleness["vault_synced_at"],
        "live_wechat_updated_at": staleness["live_wechat_updated_at"],
        "lag_minutes": staleness["lag_minutes"],
        "sync_stale": staleness["sync_stale"],
        "keyword": args.keyword,
        "count": len(page),
        "messages": page,
    }
    output(data if args.format == "json" else render_search_text(page, staleness), args.format)


def render_search_text(rows: list[dict], staleness: dict | None = None) -> str:
    banner = format_staleness_banner(staleness) if staleness else ""
    if not rows:
        return f"{banner}\n没有找到匹配消息".strip()
    body = "\n".join(f"[{row['time']}] [{row.get('chat', '')}] {row.get('sender', '')}: {row['content']}".strip() for row in rows)
    return f"{banner}\n{body}" if banner else body


def collect_stats(decrypted_dir: Path, chat: dict, start_ts: int | None, end_ts: int | None) -> dict:
    contacts, _ = load_contacts(decrypted_dir)
    total = 0
    type_counts: dict[str, int] = {}
    sender_counts: dict[str, int] = {}
    hourly = {hour: 0 for hour in range(24)}
    for db_path, table in find_chat_tables(decrypted_dir, chat):
        with connect(db_path) as con:
            name2id = load_name2id(con)
            cols = message_columns(con, table)
            clauses = []
            params = []
            if start_ts is not None:
                clauses.append(f"{cols['create_time']} >= ?")
                params.append(start_ts)
            if end_ts is not None:
                clauses.append(f"{cols['create_time']} <= ?")
                params.append(end_ts)
            where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
            for row in con.execute(f"SELECT {cols['local_type']} AS local_type, COUNT(*) AS count FROM [{table}] {where} GROUP BY {cols['local_type']}", params):
                label = type_label(row["local_type"])
                count = int(row["count"] or 0)
                type_counts[label] = type_counts.get(label, 0) + count
                total += count
            for row in con.execute(f"SELECT {cols['real_sender_id']} AS sender_id, COUNT(*) AS count FROM [{table}] {where} GROUP BY {cols['real_sender_id']}", params):
                sender_username = name2id.get(int(row["sender_id"] or 0), "")
                sender = display_name(sender_username, contacts) if sender_username else str(row["sender_id"])
                sender_counts[sender] = sender_counts.get(sender, 0) + int(row["count"] or 0)
            for row in con.execute(f"SELECT cast(strftime('%H', {cols['create_time']}, 'unixepoch', 'localtime') as integer) AS hour, COUNT(*) AS count FROM [{table}] {where} GROUP BY hour", params):
                if row["hour"] is not None:
                    hourly[int(row["hour"])] += int(row["count"] or 0)
    return {
        "total": total,
        "type_breakdown": dict(sorted(type_counts.items(), key=lambda item: item[1], reverse=True)),
        "top_senders": [{"name": name, "count": count} for name, count in sorted(sender_counts.items(), key=lambda item: item[1], reverse=True)[:10]],
        "hourly": hourly,
    }


def command_stats(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    contacts, _ = load_contacts(decrypted_dir)
    chat = resolve_chat(args.chat, contacts)
    if not chat:
        raise SystemExit(f"找不到聊天对象: {args.chat}")
    stats = collect_stats(decrypted_dir, chat, parse_time(args.start_time), parse_time(args.end_time, end_of_day=True))
    data = {"chat": chat["display_name"], "username": chat["username"], "is_group": chat.get("is_group", False), **stats}
    output(data if args.format == "json" else render_stats_text(data), args.format)


def render_stats_text(data: dict) -> str:
    lines = [f"{data['chat']} 统计", f"消息总数: {data['total']}", "", "消息类型:"]
    for label, count in data["type_breakdown"].items():
        pct = count / data["total"] * 100 if data["total"] else 0
        lines.append(f"  {label}: {count} ({pct:.1f}%)")
    lines.append("")
    lines.append("发言排行:")
    for item in data["top_senders"]:
        lines.append(f"  {item['name']}: {item['count']}")
    lines.append("")
    lines.append("24小时分布:")
    max_count = max(data["hourly"].values()) if data["hourly"] else 0
    for hour in range(24):
        count = data["hourly"].get(hour, 0)
        bar = "#" * (int(count / max_count * 24) if max_count else 0)
        lines.append(f"  {hour:02d}:00 | {bar} {count}")
    return "\n".join(lines)


def command_export(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    exports_dir = resolve_exports_dir(args.exports_dir)
    contacts, _ = load_contacts(decrypted_dir)
    chat = resolve_chat(args.chat, contacts)
    if not chat:
        raise SystemExit(f"找不到聊天对象: {args.chat}")
    rows = collect_history(
        decrypted_dir,
        chat,
        parse_time(args.start_time),
        parse_time(args.end_time, end_of_day=True),
        args.limit,
        0,
        args.type,
        args.media,
    )
    if args.format == "markdown":
        body = render_export_markdown(chat, rows, args.start_time, args.end_time)
        suffix = "md"
    else:
        body = render_messages_text(rows)
        suffix = "txt"
    out_path = Path(args.output).expanduser() if args.output else exports_dir / "cli_exports" / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{safe_name(chat['display_name'])}.{suffix}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(body.rstrip() + "\n", encoding="utf-8")
    print(out_path)
    print(f"Exported {len(rows)} messages.")


def digest_range_label(start_time: str | None, end_time: str | None) -> str:
    if start_time and end_time and start_time[:10] == end_time[:10]:
        return start_time[:10]
    if start_time or end_time:
        return f"{(start_time or 'earliest')[:10]}_{(end_time or 'latest')[:10]}"
    return datetime.now().strftime("%Y-%m-%d")


def digest_folder(data_root: Path, group: dict) -> Path:
    return data_root / f"{safe_name(group['username'])}-{safe_name(group['display_name'])}"


def last_digest_timestamp(folder: Path) -> int | None:
    history = load_json(folder / "history.json")
    value = (history.get("last_digest") or {}).get("last_message_timestamp")
    if value:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return None


def digest_stats_from_rows(rows: list[dict]) -> dict:
    counts: dict[str, int] = {}
    usable = []
    for row in rows:
        content = row.get("content") or ""
        if row.get("type") == "系统" or "revokemsg" in content:
            continue
        usable.append(row)
        sender = row.get("sender") or "未知"
        counts[sender] = counts.get(sender, 0) + 1
    leaderboard = [{"name": name, "count": count} for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True)[:10]]
    active_senders = [{"name": name, "count": count} for name, count in sorted(counts.items(), key=lambda item: item[1], reverse=True) if count >= 3]
    return {
        "message_count": len(usable),
        "leaderboard": leaderboard,
        "active_senders": active_senders,
        "last_message_timestamp": max((row["timestamp"] for row in rows), default=0),
    }


def render_digest_source_markdown(group: dict, rows: list[dict], stats: dict, range_text: str) -> str:
    lines = [
        f"{group['display_name']} 群聊精华素材 · {range_text}",
        "",
        f"消息统计: 共 {stats['message_count']} 条消息",
    ]
    for index, item in enumerate(stats["leaderboard"], 1):
        lines.append(f"{index}. {item['name']}: {item['count']} 条")
    lines.extend([
        "",
        "群友画像候选（3条以上）",
    ])
    if stats["active_senders"]:
        for item in stats["active_senders"]:
            lines.append(f"- {item['name']}: {item['count']} 条")
    else:
        lines.append("- 无")
    lines.extend([
        "",
        "消息素材",
        "",
    ])
    for row in rows:
        sender = row.get("sender") or "未知"
        lines.append(f"- id={row.get('local_id')} time={row['time']} sender={sender} type={row['type']} content={row['content']}")
    return "\n".join(lines)


def command_digest_source(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    contacts, _ = load_contacts(decrypted_dir)
    group = resolve_chat(args.group, contacts)
    if not group or not group.get("is_group"):
        raise SystemExit(f"找不到群聊: {args.group}")

    data_root = Path(args.data_root).expanduser() if args.data_root else Path.cwd() / "wechat"
    folder = digest_folder(data_root, group)
    folder.mkdir(parents=True, exist_ok=True)
    for child in ("profiles", "profiles-roast", "imgs", "sources"):
        (folder / child).mkdir(parents=True, exist_ok=True)

    start_ts = parse_time(args.start)
    if args.since_last:
        start_ts = last_digest_timestamp(folder) or start_ts
    end_ts = parse_time(args.end, end_of_day=True)
    rows = collect_history(decrypted_dir, group, start_ts, end_ts, args.limit, 0, None, args.media)
    stats = digest_stats_from_rows(rows)
    range_text = digest_range_label(args.start, args.end)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    source_json = folder / "sources" / f"{stamp}-{range_text}.json"
    source_md = folder / "sources" / f"{stamp}-{range_text}.md"
    payload = {
        "group": {"name": group["display_name"], "username": group["username"]},
        "range": {"start": args.start or "", "end": args.end or "", "since_last": args.since_last},
        "stats": stats,
        "messages": rows,
        "notes": {
            "image_content_is_opaque": True,
            "image_description_extension": str(folder / "imgs/{message_id}.txt"),
            "profiles_dir": str(folder / "profiles"),
            "history_file": str(folder / "history.json"),
        },
    }
    source_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    source_md.write_text(render_digest_source_markdown(group, rows, stats, range_text) + "\n", encoding="utf-8")
    result = {
        "folder": str(folder),
        "source_json": str(source_json),
        "source_markdown": str(source_md),
        "message_count": len(rows),
        "digest_stats_count": stats["message_count"],
        "last_message_timestamp": stats["last_message_timestamp"],
        "next_step": "Use the source files to draft a normal or roast digest, then update history.json after the final digest is accepted.",
    }
    output(result if args.format == "json" else "\n".join(f"{k}: {v}" for k, v in result.items()), args.format)


def render_export_markdown(chat: dict, rows: list[dict], start_time: str | None, end_time: str | None) -> str:
    lines = [
        f"# 聊天记录: {chat['display_name']}",
        "",
        f"- 会话 ID: {chat['username']}",
        f"- 类型: {'群聊' if chat.get('is_group') else '私聊'}",
        f"- 时间范围: {start_time or '最早'} ~ {end_time or '最新'}",
        f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 消息数量: {len(rows)}",
        "",
        "## 时间线",
        "",
    ]
    for row in rows:
        sender = f"{row['sender']}: " if row.get("sender") else ""
        lines.append(f"- {row['time']} [{row['type']}] {sender}{row['content']}")
    return "\n".join(lines)


def parse_favorite(content: str, fav_type: int) -> str:
    if not content:
        return ""
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return ""
    item = root if root.tag == "favitem" else root.find(".//favitem")
    if item is None:
        return ""
    if fav_type == 1:
        return (item.findtext("desc") or "").strip()
    if fav_type == 2:
        return "[图片收藏]"
    if fav_type == 5:
        title = (item.findtext(".//pagetitle") or "").strip()
        desc = (item.findtext(".//pagedesc") or "").strip()
        return f"{title} - {desc}" if desc else title
    if fav_type == 19:
        return (item.findtext("desc") or "").strip()
    if fav_type == 20:
        nickname = (item.findtext(".//nickname") or "").strip()
        desc = (item.findtext(".//desc") or "").strip()
        return " ".join(part for part in (nickname, desc) if part) or "[视频号]"
    return (item.findtext("desc") or "").strip() or "[收藏]"


def command_favorites(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    fav_db = decrypted_dir / "favorite/favorite.db"
    if not fav_db.exists():
        raise SystemExit(f"找不到 favorite.db: {fav_db}")
    contacts, _ = load_contacts(decrypted_dir)
    where = []
    params = []
    if args.type:
        where.append("type = ?")
        params.append(FAVORITE_TYPE_FILTERS[args.type])
    if args.query:
        where.append("content LIKE ?")
        params.append(f"%{args.query}%")
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""
    rows = []
    with connect(fav_db) as con:
        if not table_exists(con, "fav_db_item"):
            raise SystemExit("favorite.db 中没有 fav_db_item")
        for row in con.execute(
            f"SELECT local_id, type, update_time, content, fromusr, realchatname FROM fav_db_item {where_sql} ORDER BY update_time DESC LIMIT ?",
            (*params, args.limit),
        ):
            ts = int(row["update_time"] or 0)
            fav_type = int(row["type"] or 0)
            rows.append({
                "id": row["local_id"],
                "type": FAVORITE_TYPE_MAP.get(fav_type, f"type={fav_type}"),
                "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "",
                "summary": parse_favorite(row["content"] or "", fav_type),
                "from": display_name(str(row["fromusr"] or ""), contacts) if row["fromusr"] else "",
                "source_chat": display_name(str(row["realchatname"] or ""), contacts) if row["realchatname"] else "",
            })
    data = {"count": len(rows), "favorites": rows}
    output(data if args.format == "json" else render_favorites_text(rows), args.format)


URL_EXTRACT_RE = re.compile(r"https?://[^\s<>\"'」】）)]+")
INLINE_CODE_RE = re.compile(r"`[^`\n]+`")

# 匹配任意位置的 #英文词 或 #中文词（自动排除 #123 纯数字序号与 Markdown '# 标题'）
GENERIC_HASHTAG_RE = re.compile(
    r"(?<![A-Za-z0-9_/@&:=\-])#([A-Za-z][A-Za-z0-9_\-]{0,31}|[\u4e00-\u9fff][A-Za-z0-9_\-\u4e00-\u9fff]{0,15})(?![A-Za-z0-9_])"
)
# 自动识别行内简称声明，如：#resource（今后简称“#res”） / #paper(alias #p)
INLINE_ALIAS_DECL_RE = re.compile(
    r"#([A-Za-z0-9_\-\u4e00-\u9fff]+)\s*[（(][^）)]*?(?:简称|alias|即)[^#A-Za-z0-9\u4e00-\u9fff]*#?([A-Za-z0-9_\-\u4e00-\u9fff]+)[”\"'」\s]*[）)]",
    re.IGNORECASE,
)
PREFIX_NOTE_TAG_RE = re.compile(
    r"(?:^|\n)\s*(idea|todo|resource|res|paper|bug|memo|灵感|待办|资源|论文|备忘)\s*[:：—\-]",
    re.IGNORECASE,
)

BUILTIN_TAG_ALIASES: dict[str, str] = {
    "i": "idea",
    "idea": "idea",
    "ideas": "idea",
    "灵感": "idea",
    "点子": "idea",
    "t": "todo",
    "todo": "todo",
    "todos": "todo",
    "task": "todo",
    "待办": "todo",
    "r": "resource",
    "res": "resource",
    "resource": "resource",
    "resources": "resource",
    "ref": "resource",
    "reference": "resource",
    "资源": "resource",
    "参考": "resource",
    "b": "bookmark",
    "buy": "bookmark",
    "bookmark": "bookmark",
    "好物": "bookmark",
    "种草": "bookmark",
    "p": "paper",
    "paper": "paper",
    "papers": "paper",
    "论文": "paper",
}

NOISE_SHOP_OR_BOILERPLATE_RE = re.compile(
    r"(?:91kami\.com|/coupons/|【淘宝】|【闲鱼】|拼多多|yangkeduo\.com|item\.m\.jd\.com|"
    r"来自PLUS会员分享|e\.tb\.cn|m\.tb\.cn|￥[A-Za-z0-9]{6,}￥|tk=[A-Za-z0-9]+\s+HU\d+|"
    r"wj\.sf-express\.com|您的账户近期访问行为存在异常|关注我们的频道、群组,随时获取最新的学习版|"
    r"取件码|菜鸟驿站|丰巢)",
    re.IGNORECASE,
)
INTERNAL_SUB_URL_RE = re.compile(r"^https?://[^\s]+/sub/[0-9a-f]{12,}/[^\s]+$", re.IGNORECASE)
PHONE_ROSTER_LINE_RE = re.compile(r"^\s*1[3-9]\d{9}\s*\S+\s*$")
ID_CARD_RE = re.compile(r"(?:身份证号|(?<!\d)\d{17}[\dXx](?!\d))")
EPHEMERAL_PRINT_HANDOFF_RE = re.compile(r"(?:正反打印|黑白打印|彩印单面|交给\S+|签到码)", re.IGNORECASE)
HIGH_SIGNAL_DOMAIN_RE = re.compile(
    r"(?:github\.com|linux\.do|awwwards\.com|so\.qq\.com|52pojie\.cn|arxiv\.org|"
    r"huggingface\.co|news\.ycombinator\.com|arena\.site|coarena\.ai|v2ex\.com|zhihu\.com|mp\.weixin\.qq\.com)",
    re.IGNORECASE,
)


def _is_css_hex_token(token: str) -> bool:
    return (
        len(token) in (6, 8)
        and all(c in "0123456789abcdefABCDEF" for c in token)
        and any(c.isdigit() for c in token)
    )


def load_custom_tag_aliases() -> dict[str, str]:
    data = load_json(TAG_ALIAS_STATE_FILE)
    raw = data.get("aliases") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return {}
    return {str(k).strip().lower(): str(v).strip().lower() for k, v in raw.items() if k and v}


def normalize_note_tag(token: str, custom_aliases: dict[str, str] | None = None) -> str:
    low = token.strip().lstrip("#").lower()
    if custom_aliases and low in custom_aliases:
        return f"#{custom_aliases[low]}"
    if low in BUILTIN_TAG_ALIASES:
        return f"#{BUILTIN_TAG_ALIASES[low]}"
    return f"#{low}"


def extract_note_tags(
    text: str,
    custom_aliases: dict[str, str] | None = None,
) -> tuple[list[str], list[str], dict[str, str]]:
    """Return (normalized_tags, raw_tags, inline_discovered_aliases)."""
    if not text:
        return [], [], {}
    discovered: dict[str, str] = {}
    scrubbed = INLINE_CODE_RE.sub(" ", URL_EXTRACT_RE.sub(" ", text))
    for m in INLINE_ALIAS_DECL_RE.finditer(scrubbed):
        full_tok, short_tok = m.group(1).lower(), m.group(2).lower()
        canon = (custom_aliases or {}).get(full_tok) or BUILTIN_TAG_ALIASES.get(full_tok, full_tok)
        discovered[short_tok] = canon
    merged = {**(custom_aliases or {}), **discovered}

    raw_tags: list[str] = []
    norm_tags: list[str] = []
    for m in GENERIC_HASHTAG_RE.finditer(scrubbed):
        tok = m.group(1)
        if _is_css_hex_token(tok):
            continue
        rt = f"#{tok}"
        if rt not in raw_tags:
            raw_tags.append(rt)
        nt = normalize_note_tag(tok, merged)
        if nt not in norm_tags:
            norm_tags.append(nt)
    for m in PREFIX_NOTE_TAG_RE.finditer(scrubbed):
        nt = normalize_note_tag(m.group(1), merged)
        if nt not in norm_tags:
            norm_tags.append(nt)
    return norm_tags, raw_tags, discovered


def extract_idea_tags(text: str) -> list[str]:
    norm_tags, _, _ = extract_note_tags(text)
    return norm_tags


def parse_appmsg_detail(raw_xml: str) -> dict[str, str]:
    if not raw_xml or "<" not in raw_xml:
        return {}
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        try:
            root = ET.fromstring(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", raw_xml))
        except ET.ParseError:
            return {}
    return {
        "app_type": (root.findtext(".//type") or "").strip(),
        "title": (root.findtext(".//title") or "").strip(),
        "desc": (root.findtext(".//des") or "").strip(),
        "url": (root.findtext(".//url") or "").strip(),
        "appname": (root.findtext(".//appinfo/appname") or "").strip(),
        "refer_content": (root.findtext(".//refermsg/content") or "").strip(),
        "refer_svrid": (root.findtext(".//refermsg/svrid") or "").strip(),
    }


def _is_pii_or_phone_roster(text: str) -> bool:
    if not text:
        return False
    if ID_CARD_RE.search(text):
        return True
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if lines and sum(1 for ln in lines if PHONE_ROSTER_LINE_RE.match(ln)) >= max(1, len(lines) // 2):
        return True
    return False


def _redact_for_local_llm(text: str) -> str:
    masked = re.sub(r"(?<!\d)\d{17}[\dXx](?!\d)", "[REDACTED_ID]", text)
    masked = re.sub(r"(?<!\d)1[3-9]\d{9}(?!\d)", "[REDACTED_PHONE]", masked)
    return masked


def _resolve_magpie_client_config() -> tuple[str, str, str, str]:
    api_key = os.environ.get("MAGPIE_API_KEY", "").strip()
    base_url = os.environ.get("MAGPIE_BASE_URL", os.environ.get("OPENAI_COMPAT_BASE_URL", "http://" + os.environ.get("OPENAI_COMPAT_HOST", "localhost") + ":" + os.environ.get("OPENAI_COMPAT_PORT", "3425") + "/v1")).rstrip("/")
    user_agent = "vault-cli-notes"
    session_hdr = "X-Magpie-Session"
    for cfg_path in (MAGPIE_VAULT_KEY_FILE, MAGPIE_PROBE_KEY_FILE):
        if not api_key and cfg_path.exists():
            cfg = load_json(cfg_path)
            if isinstance(cfg, dict):
                api_key = str(cfg.get("api_key") or "").strip()
                base_url = str(cfg.get("base_url") or base_url).rstrip("/")
                user_agent = str(cfg.get("user_agent") or user_agent)
                session_hdr = str(cfg.get("session_header") or session_hdr)
    if not base_url.endswith("/v1"):
        base_url = f"{base_url}/v1"
    return api_key, base_url, user_agent, session_hdr


def is_pure_noise_message(base_type: int, sub_type: int, text: str, app_detail: dict[str, str]) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return True
    if base_type in (3, 34, 42, 43, 47, 48, 50, 10000, 10002):
        return True
    if base_type == 49 and (sub_type in (6, 74) or app_detail.get("app_type") in ("6", "74")):
        return True
    if stripped.startswith(("[图片]", "[视频]", "[语音", "[表情]", "[文件]")):
        return True
    probe = " ".join(p for p in (stripped, app_detail.get("url", ""), app_detail.get("appname", "")) if p)
    if NOISE_SHOP_OR_BOILERPLATE_RE.search(probe):
        return True
    if INTERNAL_SUB_URL_RE.match(stripped):
        return True
    if _is_pii_or_phone_roster(stripped) or _is_pii_or_phone_roster(app_detail.get("refer_content", "")):
        return True
    if re.fullmatch(r"[A-Za-z0-9_\-]{16,128}", stripped):
        return True
    return False


def rerank_notes_via_magpie(
    items: list[dict],
    query: str,
    *,
    top_n: int | None = None,
    model: str = DEFAULT_RERANK_MODEL,
    timeout_sec: int = 60,
) -> tuple[list[dict], str]:
    """Semantic ranking via local MagPie :3425/v1/rerank (ProxyHandler({}) direct loopback)."""
    clean_q = (query or "").strip()
    if not items or not clean_q:
        return items, "empty"

    api_key, base_url, user_agent, session_hdr = _resolve_magpie_client_config()
    if not api_key:
        return items[: top_n] if top_n else items, "skipped:no_magpie_key"

    documents = []
    for it in items:
        tag_part = " ".join(it.get("tags") or [])
        url_part = " ".join(it.get("urls") or [])
        body = _redact_for_local_llm(it.get("content", ""))[:2000]
        doc = "\n".join(p for p in (tag_part, body, url_part) if p).strip() or "(empty note)"
        documents.append(doc)

    limit = min(len(documents), max(1, top_n)) if top_n else len(documents)
    req_payload = json.dumps(
        {
            "model": model,
            "query": clean_q,
            "documents": documents,
            "top_n": limit,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/rerank",
        data=req_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": user_agent,
            session_hdr: "vault-cli-notes-rerank",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=max(10, int(timeout_sec))) as resp:
            resp_json = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return items[:limit], f"degraded:http_{exc.code}"
    except Exception as exc:
        return items[:limit], f"degraded:{type(exc).__name__}"

    ranked_rows = resp_json.get("results") or resp_json.get("data") or []
    reranked: list[dict] = []
    seen_indices: set[int] = set()
    for row in ranked_rows:
        if not isinstance(row, dict):
            continue
        idx = row.get("index")
        score = row.get("relevance_score")
        if isinstance(idx, int) and 0 <= idx < len(items) and idx not in seen_indices:
            enriched = dict(items[idx])
            if isinstance(score, (int, float)):
                enriched["rerank_score"] = round(float(score), 6)
            enriched["rerank_model"] = model
            reranked.append(enriched)
            seen_indices.add(idx)

    if not reranked:
        return items[:limit], "degraded:empty_results"
    return reranked[:limit], f"ok:{model}"


def enrich_notes_via_magpie(
    items: list[dict],
    *,
    model: str = "group/flash",
    timeout_sec: int = 120,
) -> tuple[list[dict], str]:
    """Optional semantic structuring via local MagPie :3425 (zero proxy detour, graceful degradation)."""
    if not items:
        return items, "empty"

    api_key, base_url, user_agent, session_hdr = _resolve_magpie_client_config()
    if not api_key:
        return items, "skipped:no_magpie_key"

    batch_input = [
        {
            "idx": i,
            "raw_tags": it.get("raw_tags", []),
            "urls": it.get("urls", []),
            "text": _redact_for_local_llm(it.get("content", ""))[:1200],
        }
        for i, it in enumerate(items)
    ]
    sys_prompt = (
        "你是本地个人知识库结构化引擎。对输入的微信文件传输助手候选笔记做语义分类，严格只输出合法的 JSON 数组（不要 Markdown 代码块）。"
        "每个元素格式为：{\"idx\": int, \"keep\": bool, \"category\": \"idea\"|\"resource\"|\"todo\"|\"reference\"|\"memo\"|\"noise\", "
        "\"suggested_tags\": [\"#...\"], \"title\": \"25字内精炼标题\"}。"
        "若条目显式带有用户 #标签 则 keep 必为 true；纯电商比价、快递取件、系统风控弹窗或广告导流则 keep=false, category=\"noise\"。"
    )
    req_payload = json.dumps(
        {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": json.dumps(batch_input, ensure_ascii=False)},
            ],
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=req_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": user_agent,
            session_hdr: "vault-cli-notes",
        },
        method="POST",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=max(115, int(timeout_sec))) as resp:
            resp_json = json.loads(resp.read().decode("utf-8"))
        raw_reply = (resp_json.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()
        raw_reply = re.sub(r"^\x60{3}(?:json)?\s*|\s*\x60{3}$", "", raw_reply, flags=re.S).strip()
        parsed = json.loads(raw_reply)
        if not isinstance(parsed, list):
            return items, "degraded:non_list_json"
    except urllib.error.HTTPError as exc:
        return items, f"degraded:http_{exc.code}"
    except Exception as exc:
        return items, f"degraded:{type(exc).__name__}"

    by_idx = {int(entry["idx"]): entry for entry in parsed if isinstance(entry, dict) and "idx" in entry}
    filtered: list[dict] = []
    for i, it in enumerate(items):
        verdict = by_idx.get(i)
        if verdict:
            if not it.get("is_tagged") and verdict.get("keep") is False:
                continue
            it["llm"] = {
                "model": resp_json.get("model", model),
                "category": verdict.get("category", ""),
                "title": verdict.get("title", ""),
                "suggested_tags": verdict.get("suggested_tags") or [],
            }
        filtered.append(it)
    return filtered, f"ok:{model}"


def collect_notes(
    decrypted_dir: Path,
    *,
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 50,
    include_untagged: bool = True,
    tag_filter: str | None = None,
    save_aliases: bool = False,
) -> list[dict]:
    contacts, _ = load_contacts(decrypted_dir)
    custom_aliases = load_custom_tag_aliases()
    newly_discovered_aliases: dict[str, str] = {}
    items: list[dict] = []

    fh_chat = resolve_chat("filehelper", contacts) or {
        "username": "filehelper",
        "display_name": "文件传输助手",
        "is_group": False,
    }
    raw_fh: list[dict] = []
    for db_path, table in find_chat_tables(decrypted_dir, fh_chat):
        with connect_readonly(db_path) as con:
            cols = message_columns(con, table)
            adj_start = (start_ts - 300) if start_ts is not None else None
            sql, params = build_select_sql(table, cols, adj_start, end_ts, None, None, None, 0)
            for row in con.execute(sql, params):
                local_type = row["local_type"]
                base_type, sub_type = split_msg_type(local_type)
                ts = int(row["create_time"] or 0)
                raw_text = decode_value(row["message_content"], row["compression_flag"]) or decode_value(
                    row["compress_content"], row["compression_flag"]
                )
                _, raw_text = parse_sender_prefix(raw_text)
                app_detail = parse_appmsg_detail(raw_text) if base_type == 49 else {}
                formatted = format_content(local_type, raw_text, False, None, "filehelper", ts)
                shop_probe = " ".join(
                    p for p in (formatted, app_detail.get("url", ""), app_detail.get("appname", "")) if p
                )
                raw_fh.append(
                    {
                        "local_id": row["local_id"],
                        "server_id": str(row["server_id"] or ""),
                        "timestamp": ts,
                        "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
                        "base_type": base_type,
                        "sub_type": sub_type,
                        "raw_text": raw_text,
                        "formatted": formatted,
                        "app_detail": app_detail,
                        "is_shop_noise": bool(NOISE_SHOP_OR_BOILERPLATE_RE.search(shop_probe)),
                    }
                )
    raw_fh.sort(key=lambda r: (r["timestamp"], int(r["local_id"] or 0)))

    consumed_indices: set[int] = set()
    for idx, cur in enumerate(raw_fh):
        if idx in consumed_indices:
            continue
        ts = cur["timestamp"]
        bt, st = cur["base_type"], cur["sub_type"]
        if bt in (3, 34, 42, 43, 47, 48, 50, 10000, 10002):
            continue
        app_d = cur["app_detail"]
        if bt == 49 and (st in (6, 74) or app_d.get("app_type") in ("6", "74")):
            continue

        text = cur["formatted"]
        searchable = "\n".join(
            p for p in (text, app_d.get("title", ""), app_d.get("desc", ""), app_d.get("refer_content", "")) if p
        )
        tags, raw_tags, disc = extract_note_tags(searchable, custom_aliases)
        if disc:
            custom_aliases.update(disc)
            newly_discovered_aliases.update(disc)

        extra_notes: list[str] = []
        extra_urls: list[str] = []
        j = idx + 1
        while j < len(raw_fh):
            nxt = raw_fh[j]
            dt_sec = nxt["timestamp"] - ts
            if dt_sec < 0 or dt_sec > 300:
                break
            n_bt, n_st = nxt["base_type"], nxt["sub_type"]
            n_app = nxt["app_detail"]
            if n_bt in (3, 34, 42, 43, 47, 48, 50, 10000, 10002):
                break
            if n_bt == 49 and (n_st in (6, 74) or n_app.get("app_type") in ("6", "74")):
                break

            nxt_tags, nxt_raw, nxt_disc = extract_note_tags(nxt["formatted"], custom_aliases)
            if nxt_disc:
                custom_aliases.update(nxt_disc)
                newly_discovered_aliases.update(nxt_disc)

            cur_has_link = (bt == 49 and app_d.get("app_type") not in ("6", "74", "57")) or bool(
                URL_EXTRACT_RE.search(text)
            )
            nxt_has_link = (n_bt == 49 and n_app.get("app_type") not in ("6", "74", "57")) or bool(
                URL_EXTRACT_RE.search(nxt["formatted"])
            )
            is_link_then_tag = cur_has_link and n_bt == 1 and bool(nxt_tags) and dt_sec <= 300
            is_tag_then_link = bool(tags) and not cur_has_link and nxt_has_link and dt_sec <= 180
            is_rapid_text_burst = (
                bt == 1
                and n_bt == 1
                and not cur_has_link
                and not nxt_has_link
                and len(text) >= 40
                and len(nxt["formatted"]) >= 40
                and (nxt["timestamp"] - raw_fh[j - 1]["timestamp"]) <= 15
            )
            if is_link_then_tag or is_tag_then_link or is_rapid_text_burst:
                for t in nxt_tags:
                    if t not in tags:
                        tags.append(t)
                for rt in nxt_raw:
                    if rt not in raw_tags:
                        raw_tags.append(rt)
                extra_notes.append(nxt["formatted"].strip())
                if n_app.get("url"):
                    extra_urls.append(n_app["url"])
                consumed_indices.add(j)
                ts = max(ts, nxt["timestamp"])
                j += 1
            else:
                break

        if start_ts is not None and ts < start_ts:
            continue
        if end_ts is not None and ts > end_ts:
            continue

        combined_text = text
        if app_d.get("desc") and app_d["desc"] not in combined_text:
            combined_text = f"{combined_text}\n{app_d['desc']}".strip()
        if extra_notes:
            combined_text = "\n\n".join([combined_text, *extra_notes]).strip()

        urls: list[str] = []
        for u_cand in [app_d.get("url", ""), *extra_urls, *URL_EXTRACT_RE.findall(combined_text + "\n" + app_d.get("refer_content", ""))]:
            u_clean = (u_cand or "").strip().rstrip(".,;!?，。；！？")
            if u_clean.startswith("http") and u_clean not in urls:
                urls.append(u_clean)

        is_tagged = bool(tags)
        if not is_tagged:
            if not include_untagged:
                continue
            if cur["is_shop_noise"] or is_pure_noise_message(bt, st, combined_text, app_d):
                continue
            near_shop = any(
                abs(raw_fh[k]["timestamp"] - cur["timestamp"]) <= 180 and raw_fh[k]["is_shop_noise"]
                for k in range(max(0, idx - 3), min(len(raw_fh), idx + 4))
                if k != idx
            )
            if near_shop and len(combined_text) <= 24:
                continue
            near_pdf = any(
                0 <= (cur["timestamp"] - raw_fh[k]["timestamp"]) <= 15
                and raw_fh[k]["base_type"] == 49
                and raw_fh[k]["sub_type"] in (6, 74)
                for k in range(max(0, idx - 2), idx)
            )
            if near_pdf and EPHEMERAL_PRINT_HANDOFF_RE.search(combined_text):
                continue

            non_url_body = URL_EXTRACT_RE.sub("", combined_text).strip()
            if urls and len(non_url_body) >= 6:
                tags = ["untagged-resource"]
            elif bt == 49 and app_d.get("app_type") == "5":
                tags = ["untagged-article"]
            elif len(non_url_body) >= 28:
                tags = ["untagged-note"]
            elif urls and any(HIGH_SIGNAL_DOMAIN_RE.search(u) for u in urls):
                tags = ["untagged-link"]
            else:
                continue

        items.append(
            {
                "source": "filehelper",
                "id": cur["local_id"],
                "timestamp": ts,
                "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
                "is_tagged": is_tagged,
                "tags": tags,
                "raw_tags": raw_tags,
                "content": combined_text,
                "urls": urls,
            }
        )

    # 2. Scan favorite.db (read-only)
    fav_db = decrypted_dir / "favorite/favorite.db"
    if fav_db.exists():
        with connect_readonly(fav_db) as con:
            if table_exists(con, "fav_db_item"):
                fav_tag_map: dict[int, list[str]] = {}
                if table_exists(con, "fav_tag_db_item") and table_exists(con, "fav_bind_tag_db_item"):
                    try:
                        for r in con.execute(
                            "SELECT b.fav_local_id AS fid, t.name AS tname "
                            "FROM fav_bind_tag_db_item b JOIN fav_tag_db_item t ON b.tag_local_id = t.local_id"
                        ):
                            if r["tname"]:
                                fav_tag_map.setdefault(int(r["fid"]), []).append(str(r["tname"]))
                    except sqlite3.Error:
                        pass

                for row in con.execute(
                    "SELECT local_id, type, update_time, content, fromusr, realchatname FROM fav_db_item ORDER BY update_time DESC"
                ):
                    ts = int(row["update_time"] or 0)
                    if start_ts is not None and ts < start_ts:
                        continue
                    if end_ts is not None and ts > end_ts:
                        continue
                    fav_type = int(row["type"] or 0)
                    raw_xml = row["content"] or ""
                    summary = parse_favorite(raw_xml, fav_type)
                    xml_tags: list[str] = list(fav_tag_map.get(int(row["local_id"]), []))
                    urls = []
                    try:
                        root = ET.fromstring(raw_xml)
                        for tn in root.findall(".//taglist/tag"):
                            if tn.text and tn.text.strip() and tn.text.strip() not in xml_tags:
                                xml_tags.append(tn.text.strip())
                        for ln in root.findall(".//link"):
                            if ln.text and ln.text.strip().startswith("http"):
                                u = ln.text.strip()
                                if u not in urls:
                                    urls.append(u)
                    except ET.ParseError:
                        pass
                    for u in URL_EXTRACT_RE.findall(summary):
                        u_clean = u.rstrip(".,;!?，。；！？")
                        if u_clean not in urls:
                            urls.append(u_clean)

                    tags, raw_tags, disc = extract_note_tags(summary, custom_aliases)
                    if disc:
                        custom_aliases.update(disc)
                        newly_discovered_aliases.update(disc)
                    for xt in xml_tags:
                        rt = f"#{xt.lstrip('#')}"
                        nt = normalize_note_tag(xt, custom_aliases)
                        if rt not in raw_tags:
                            raw_tags.append(rt)
                        if nt not in tags:
                            tags.append(nt)

                    is_tagged = bool(tags)
                    if not is_tagged:
                        if not include_untagged or fav_type in (2, 8):
                            continue
                        if not summary or NOISE_SHOP_OR_BOILERPLATE_RE.search(summary) or _is_pii_or_phone_roster(summary):
                            continue
                        if re.fullmatch(r"[A-Za-z0-9+/=_\-]{24,}", summary.strip()):
                            continue
                        tags = ["untagged-fav"]

                    items.append(
                        {
                            "source": "favorite.db",
                            "id": row["local_id"],
                            "timestamp": ts,
                            "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S") if ts else "",
                            "is_tagged": is_tagged,
                            "tags": tags,
                            "raw_tags": raw_tags,
                            "content": summary,
                            "urls": urls,
                        }
                    )

    if save_aliases and newly_discovered_aliases:
        save_json(
            TAG_ALIAS_STATE_FILE,
            {
                "updated_at": datetime.now().isoformat(timespec="seconds"),
                "aliases": custom_aliases,
            },
        )

    if tag_filter:
        norm_target = normalize_note_tag(tag_filter, custom_aliases)
        raw_target = f"#{tag_filter.strip().lstrip('#').lower()}"
        items = [
            it
            for it in items
            if norm_target in it["tags"]
            or any(rt.lower() == raw_target for rt in it.get("raw_tags", []))
            or tag_filter.lower() in [t.lower().lstrip("#") for t in it["tags"]]
        ]

    items.sort(key=lambda item: item["timestamp"], reverse=True)
    items = items[: max(1, limit)]
    items.sort(key=lambda item: item["timestamp"])
    return items


def collect_ideas(
    decrypted_dir: Path,
    *,
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 50,
    include_untagged: bool = True,
) -> list[dict]:
    return collect_notes(
        decrypted_dir,
        start_ts=start_ts,
        end_ts=end_ts,
        limit=limit,
        include_untagged=include_untagged,
    )


def render_notes_text(
    items: list[dict],
    llm_status: str = "",
    rerank_status: str = "",
    staleness: dict | None = None,
) -> str:
    banner = format_staleness_banner(staleness) if staleness else ""
    if not items:
        msg = "未找到匹配的笔记/灵感条目（支持任意 #标签 如 #res / #idea / #todo / #paper 及无标签高信号资源；仅看显式标签可加 --tagged-only）"
        return f"{banner}\n{msg}".strip()
    head = f"共提取 {len(items)} 条个人笔记/灵感记录"
    badges = [b for b in (f"语义重排: {rerank_status}" if rerank_status else "", f"LLM 结构化: {llm_status}" if llm_status else "") if b]
    if badges:
        head += f"（{' | '.join(badges)}）"
    lines = [banner, ""] if banner else []
    lines.extend([f"{head}：", ""])
    for idx, item in enumerate(items, 1):
        tag_str = " ".join(item["tags"])
        raw_diff = [rt for rt in item.get("raw_tags", []) if rt.lower() not in [t.lower() for t in item["tags"]]]
        raw_hint = f" (原标: {' '.join(raw_diff)})" if raw_diff else ""
        score_hint = f" [score={item['rerank_score']:.4f}]" if "rerank_score" in item else ""
        lines.append(f"{idx}. [{item['time']}] ({item['source']}) {tag_str}{raw_hint}{score_hint}")
        if item.get("llm") and item["llm"].get("title"):
            lines.append(f"   [摘要] [{item['llm'].get('category', '')}] {item['llm']['title']}")
        for ln in item["content"].splitlines():
            lines.append(f"   {ln}")
        for u in item.get("urls") or []:
            if u not in item["content"]:
                lines.append(f"   URL: {u}")
        lines.append("")
    return "\n".join(lines).rstrip()


def command_notes(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    staleness = maybe_sync_if_stale(args, decrypted_dir)
    start_ts = parse_time(args.since) if args.since else None
    end_ts = parse_time(args.end, end_of_day=True) if args.end else None
    include_untagged = not bool(getattr(args, "tagged_only", False))
    semantic_query = (getattr(args, "semantic_query", "") or "").strip()
    fetch_limit = max(args.limit * 5, 250) if semantic_query else args.limit
    items = collect_notes(
        decrypted_dir,
        start_ts=start_ts,
        end_ts=end_ts,
        limit=fetch_limit,
        include_untagged=include_untagged,
        tag_filter=getattr(args, "tag", None),
        save_aliases=bool(getattr(args, "save_aliases", False)),
    )
    rerank_status = ""
    if semantic_query:
        items, rerank_status = rerank_notes_via_magpie(
            items,
            semantic_query,
            top_n=args.limit,
            timeout_sec=60,
        )
    llm_status = ""
    if getattr(args, "llm", False):
        items, llm_status = enrich_notes_via_magpie(
            items,
            model=getattr(args, "llm_model", "group/flash"),
        )
    payload = {
        "vault_synced_at": staleness["vault_synced_at"],
        "live_wechat_updated_at": staleness["live_wechat_updated_at"],
        "lag_minutes": staleness["lag_minutes"],
        "sync_stale": staleness["sync_stale"],
        "since": args.since or "",
        "end": args.end or "",
        "include_untagged": include_untagged,
        "tag_filter": getattr(args, "tag", "") or "",
        "semantic_query": semantic_query,
        "rerank_status": rerank_status or "off",
        "llm_status": llm_status or "off",
        "count": len(items),
        "notes": items,
        "ideas": items,  # 100% 向下兼容旧调用方读取 payload["ideas"]
    }
    output(
        payload if args.format == "json" else render_notes_text(items, llm_status, rerank_status, staleness),
        args.format,
    )


command_ideas = command_notes


def render_favorites_text(rows: list[dict]) -> str:
    if not rows:
        return "没有找到收藏"
    lines = []
    for row in rows:
        entry = f"[{row['time']}] [{row['type']}] {row['summary']}"
        if row["from"]:
            entry += f"\n  来自: {row['from']}"
        if row["source_chat"]:
            entry += f"\n  聊天: {row['source_chat']}"
        lines.append(entry)
    return "\n\n".join(lines)


def xml_text(root: ET.Element, path: str) -> str:
    node = root.find(path)
    return (node.text or "").strip() if node is not None else ""


def parse_moment(content: str, tid: str, db_user: str) -> dict:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        root = ET.fromstring(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", content))
    timeline = root.find("TimelineObject") if root.tag != "TimelineObject" else root
    if timeline is None:
        timeline = root
    media = []
    for item in timeline.findall(".//media"):
        media.append({
            "type": xml_text(item, "type"),
            "url": xml_text(item, "url"),
            "thumb": xml_text(item, "thumb"),
        })
    links = []
    for path in ("ContentObject/contentUrl", ".//url"):
        for node in timeline.findall(path):
            if node.text and node.text.strip():
                links.append(node.text.strip())
    create_time = xml_text(timeline, "createTime")
    ts = int(create_time) if create_time.isdigit() else 0
    return {
        "tid": tid,
        "username": xml_text(timeline, "username") or db_user,
        "nickname": xml_text(timeline, "nickname"),
        "timestamp": ts,
        "time": datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "",
        "content": xml_text(timeline, "contentDesc"),
        "type": xml_text(timeline, "ContentObject/contentStyle") or xml_text(timeline, "ContentObject/contentSubStyle"),
        "media": media,
        "links": sorted(set(links)),
    }


def command_moments(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    sns_db = decrypted_dir / "sns/sns.db"
    if not sns_db.exists():
        raise SystemExit(f"找不到 sns.db: {sns_db}")
    contacts, _ = load_contacts(decrypted_dir)
    usernames = set(args.username or [])
    if args.name:
        q = args.name.lower()
        for item in contacts.values():
            if any(q in str(item.get(field) or "").lower() for field in ("username", "display_name", "remark", "nick_name", "alias")):
                usernames.add(item["username"])
    if args.name and not usernames:
        output({"count": 0, "moments": []} if args.format == "json" else "没有找到匹配朋友圈", args.format)
        return
    start_ts = parse_time(args.start)
    end_ts = parse_time(args.end, end_of_day=True)
    posts = []
    with connect(sns_db) as con:
        if usernames:
            placeholders = ",".join("?" for _ in usernames)
            query_iter = con.execute(f"SELECT tid, user_name, content FROM SnsTimeLine WHERE user_name IN ({placeholders})", tuple(usernames))
        else:
            query_iter = con.execute("SELECT tid, user_name, content FROM SnsTimeLine")
        for row in query_iter:
            if not row["content"]:
                continue
            try:
                post = parse_moment(row["content"], str(row["tid"]), str(row["user_name"]))
            except Exception as exc:
                post = {"tid": str(row["tid"]), "username": str(row["user_name"]), "time": "", "timestamp": 0, "content": f"[无法解析 XML: {exc}]", "media": [], "links": []}
            if start_ts and (not post["timestamp"] or post["timestamp"] < start_ts):
                continue
            if end_ts and (not post["timestamp"] or post["timestamp"] > end_ts):
                continue
            if args.keyword:
                haystack = json.dumps(post, ensure_ascii=False)
                if args.keyword.lower() not in haystack.lower():
                    continue
            post["display_name"] = display_name(post["username"], contacts)
            posts.append(post)
    posts.sort(key=lambda item: item["timestamp"], reverse=True)
    posts = posts[: args.limit]
    data = {"count": len(posts), "moments": posts}
    output(data if args.format == "json" else render_moments_text(posts), args.format)


def render_moments_text(posts: list[dict]) -> str:
    if not posts:
        return "没有找到匹配朋友圈"
    lines = []
    for post in posts:
        suffix = []
        if post.get("media"):
            suffix.append(f"{len(post['media'])}个媒体")
        if post.get("links"):
            suffix.append(f"{len(post['links'])}个链接")
        header = f"[{post['time']}] {post.get('display_name') or post['username']}"
        if suffix:
            header += f" ({'，'.join(suffix)})"
        lines.append(header)
        lines.append(post.get("content") or "[无文字内容]")
        for link in post.get("links", [])[:5]:
            lines.append(f"  link: {link}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _add_sync_if_stale_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--sync-if-stale",
        dest="sync_if_stale",
        action="store_true",
        default=argparse.SUPPRESS,
        help="若检测到离线明文库落后实时微信 db_storage，先执行纯离线缓存密钥增量解密 (decrypt_db.py -i，零进程接触)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the local Mac vault or an explicit Windows plaintext snapshot.")
    parser.add_argument("--decrypted-dir", help="覆盖明文 vault 目录")
    parser.add_argument(
        "--sync-if-stale",
        action="store_true",
        help="若检测到离线明文库落后实时微信 db_storage，先执行纯离线缓存密钥增量解密 (decrypt_db.py -i，零进程接触)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("status", help="查看 vault 可用数据库与实时滞后状态")
    p.add_argument("--format", choices=["json", "text"], default="text")
    _add_sync_if_stale_arg(p)
    p.set_defaults(func=command_status)

    p = sub.add_parser("sessions", aliases=["recent"], help="最近会话（别名 recent）")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--format", choices=["json", "text"], default="json")
    _add_sync_if_stale_arg(p)
    p.set_defaults(func=command_sessions)

    p = sub.add_parser("unread", help="未读会话")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--format", choices=["json", "text"], default="json")
    _add_sync_if_stale_arg(p)
    p.set_defaults(func=command_unread)

    p = sub.add_parser("new-messages", help="自上次调用以来的新消息")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=command_new_messages)

    p = sub.add_parser("contacts", help="联系人/群聊搜索")
    p.add_argument("--query")
    p.add_argument("--detail")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=command_contacts)

    p = sub.add_parser(
        "contacts-audit",
        help="纯离线只读联系人治理审计（无备注好友、contact_label 标签分布、重名好友、共同群聊数统计）",
    )
    p.add_argument("--json", dest="as_json", action="store_true", help="输出结构化 JSON（等价于 --format json）")
    p.add_argument("--format", choices=["markdown", "text", "json"], default="markdown", help="输出格式（默认 markdown 摘要）")
    p.add_argument("--limit", type=int, default=50, help="Markdown 摘要各明细表最大展示行数（0 表示不截断；JSON 始终输出完整列表）")
    p.add_argument("--include-openim", action="store_true", help="将已添加的企业微信/OpenIM 联系人（local_type=5）一并纳入审计")
    p.add_argument("--redact", action="store_true", help="对输出的 wxid/微信号与姓名中间字符做脱敏掩码（用于日志或汇报抽样）")
    p.set_defaults(func=command_contacts_audit)

    p = sub.add_parser("members", help="群成员")
    p.add_argument("group")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=command_members)

    p = sub.add_parser("history", help="聊天记录")
    p.add_argument("chat")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--start-time", default="")
    p.add_argument("--end-time", default="")
    p.add_argument("--type", choices=sorted(MESSAGE_TYPE_FILTERS))
    p.add_argument("--media", action="store_true", help="尝试附带本地文件路径提示")
    p.add_argument("--format", choices=["json", "text"], default="json")
    _add_sync_if_stale_arg(p)
    p.set_defaults(func=command_history)

    p = sub.add_parser("search", help="全局或指定会话搜索")
    p.add_argument("keyword")
    p.add_argument("--chat", action="append")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--start-time", default="")
    p.add_argument("--end-time", default="")
    p.add_argument("--type", choices=sorted(MESSAGE_TYPE_FILTERS))
    p.add_argument("--format", choices=["json", "text"], default="json")
    _add_sync_if_stale_arg(p)
    p.set_defaults(func=command_search)

    p = sub.add_parser("stats", help="聊天统计")
    p.add_argument("chat")
    p.add_argument("--start-time", default="")
    p.add_argument("--end-time", default="")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=command_stats)

    p = sub.add_parser("export", help="导出聊天记录")
    p.add_argument("chat")
    p.add_argument("--format", choices=["markdown", "txt"], default="markdown")
    p.add_argument("--output")
    p.add_argument("--exports-dir")
    p.add_argument("--start-time", default="")
    p.add_argument("--end-time", default="")
    p.add_argument("--limit", type=int, default=500)
    p.add_argument("--type", choices=sorted(MESSAGE_TYPE_FILTERS))
    p.add_argument("--media", action="store_true")
    p.set_defaults(func=command_export)

    p = sub.add_parser("digest-source", help="生成群聊摘要素材包")
    p.add_argument("group")
    p.add_argument("--start", help="开始时间 YYYY-MM-DD [HH:MM[:SS]]")
    p.add_argument("--end", help="结束时间 YYYY-MM-DD [HH:MM[:SS]]")
    p.add_argument("--since-last", action="store_true", help="优先从该群 history.json 的上次摘要时间继续")
    p.add_argument("--data-root", help="摘要归档根目录，默认当前项目的 wechat/")
    p.add_argument("--limit", type=int, default=5000)
    p.add_argument("--media", action="store_true", help="尝试附带本地文件路径提示")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=command_digest_source)

    p = sub.add_parser("favorites", help="收藏夹")
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--type", choices=sorted(FAVORITE_TYPE_FILTERS))
    p.add_argument("--query")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=command_favorites)

    p = sub.add_parser(
        "notes",
        aliases=["ideas"],
        help="零副作用离线扫描 filehelper 与 favorite.db 中的个人笔记/资源/灵感（支持任意 #标签 与无标签高信号条目）",
    )
    p.add_argument("--since", "--start", dest="since", default="", help="起始日期 YYYY-MM-DD [HH:MM[:SS]]")
    p.add_argument("--end", default="", help="结束日期 YYYY-MM-DD [HH:MM[:SS]]")
    p.add_argument("--limit", type=int, default=50, help="返回最大条数（默认 50）")
    p.add_argument("--tag", default="", help="按特定标签过滤（如 res / resource / idea / todo / paper）")
    p.add_argument("--tagged-only", action="store_true", help="仅返回带有显式 #标签 的条目")
    p.add_argument("--include-untagged", action="store_true", default=True, help="兼容旧参数：默认已开启高信号无标签笔记提取")
    p.add_argument("--save-aliases", action="store_true", help="将消息中声明的新标签简称（如 #resource（简称#res））持久化至 state/note_tag_aliases.json")
    p.add_argument("--semantic-query", default="", help="通过本地 MagPie :3425/v1/rerank (moark/Qwen3-Reranker-4B) 按语义相关性排序候选笔记")
    p.add_argument("--llm", action="store_true", help="通过本地 MagPie :3425 (默认 group/flash) 执行语义分类与标题提炼")
    p.add_argument("--llm-model", default="group/flash", help="指定本地 MagPie 确定性模型组（默认 group/flash，超时 >=115s）")
    p.add_argument("--format", choices=["json", "text"], default="json")
    _add_sync_if_stale_arg(p)
    p.set_defaults(func=command_notes)

    p = sub.add_parser("moments", help="朋友圈")
    p.add_argument("--name")
    p.add_argument("--username", action="append")
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--keyword")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=command_moments)

    p = sub.add_parser("sync-aliases", help="扫描系统消息与联系人库，同步群聊曾用名与联系人备注/原昵称映射至资料库索引")
    p.add_argument("--exports-dir")
    p.add_argument("--format", choices=["json", "text"], default="json")
    p.set_defaults(func=command_sync_aliases)
    return parser


def _strip_export_file_label(filename: str, username: str) -> str:
    stem = Path(filename).stem
    for prefix in ("group_", "single_"):
        if stem.startswith(prefix):
            stem = stem[len(prefix):]
            break
    if "__" in stem:
        stem = stem.split("__", 1)[0]
    if stem == username or stem.startswith("wxid_") or stem.endswith("@chatroom"):
        return ""
    return stem.strip()


def command_sync_aliases(args: argparse.Namespace) -> None:
    decrypted_dir = resolve_decrypted_dir(args.decrypted_dir)
    exports_dir = resolve_exports_dir(getattr(args, "exports_dir", None))
    contacts, _ = load_contacts(decrypted_dir)

    plain_re = re.compile(r"修改群名为[“\"「]([^$”\"」]+?)[”\"」]")
    xml_re = re.compile(r'<link\s+name="remark"[^>]*>.*?<plain><!\[CDATA\[(.*?)\]\]></plain>', re.DOTALL)

    renames_by_user: dict[str, list[str]] = {}
    for db_path in message_dbs(decrypted_dir):
        with connect(db_path) as con:
            tables = [row["name"] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'")]
            for table in tables:
                uname = username_for_table(table, con) or username_for_table_from_contacts(table, contacts) or table
                try:
                    for row in con.execute(
                        f"SELECT create_time, local_type, message_content, compress_content, WCDB_CT_message_content FROM [{table}] WHERE (local_type & 4294967295) = 10000 ORDER BY create_time ASC"
                    ):
                        txt = decode_value(row["message_content"], row["WCDB_CT_message_content"]) or decode_value(row["compress_content"], row["WCDB_CT_message_content"])
                        if "修改群名为" not in txt:
                            continue
                        for m in xml_re.findall(txt):
                            val = m.strip()
                            if val and "\t" not in val and "\n" not in val:
                                renames_by_user.setdefault(uname, []).append(val)
                        for m in plain_re.findall(txt):
                            val = m.strip()
                            if val and val != "$remark$" and "\t" not in val and "\n" not in val:
                                renames_by_user.setdefault(uname, []).append(val)
                except sqlite3.Error:
                    continue

    # Merge with _export_index.json
    idx_path = exports_dir / "_export_index.json"
    idx_data = load_json(idx_path)
    chats_idx = idx_data.get("chats") if isinstance(idx_data, dict) else None
    updated_idx_entries = 0
    by_username: dict[str, dict] = {}

    all_usernames = set(contacts.keys()) | set(renames_by_user.keys()) | (set(chats_idx.keys()) if isinstance(chats_idx, dict) else set())
    for uname in sorted(all_usernames):
        c = contacts.get(uname, {})
        idx_entry = chats_idx.get(uname, {}) if isinstance(chats_idx, dict) else {}
        cur_name = c.get("display_name") or idx_entry.get("current_chat_name") or uname
        nick = c.get("nick_name") or idx_entry.get("nick_name") or ""
        remark = c.get("remark") or idx_entry.get("remark") or ""
        alias = c.get("alias") or idx_entry.get("alias") or ""

        prev_candidates: list[str] = []
        for fn in (idx_entry.get("previous_files") or []):
            lbl = _strip_export_file_label(str(fn), uname)
            if lbl:
                prev_candidates.append(lbl)
        for pn in (idx_entry.get("previous_names") or []):
            if isinstance(pn, str) and pn.strip():
                prev_candidates.append(pn.strip())
        for rn in renames_by_user.get(uname, []):
            prev_candidates.append(rn)

        dedup_prev: list[str] = []
        for item in prev_candidates:
            if item and item != cur_name and item not in dedup_prev:
                dedup_prev.append(item)

        if nick or remark or alias or dedup_prev:
            by_username[uname] = {
                "display_name": cur_name,
                "nick_name": nick,
                "remark": remark,
                "alias": alias,
                "previous_names": dedup_prev,
            }

        if isinstance(chats_idx, dict) and uname in chats_idx:
            entry = chats_idx[uname]
            entry["nick_name"] = nick
            entry["remark"] = remark
            entry["alias"] = alias
            entry["previous_names"] = dedup_prev
            updated_idx_entries += 1

    save_json(ALIAS_STATE_FILE, {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "by_username": by_username,
    })
    if isinstance(chats_idx, dict) and idx_path.exists():
        idx_path.write_text(json.dumps(idx_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "alias_state_file": str(ALIAS_STATE_FILE),
        "export_index_file": str(idx_path),
        "groups_with_rename_history": len(renames_by_user),
        "total_alias_records": len(by_username),
        "updated_export_index_entries": updated_idx_entries,
    }
    output(summary if args.format == "json" else "\n".join(f"{k}: {v}" for k, v in summary.items()), args.format)


def main(argv: list[str] | None = None) -> int | None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    args = parser.parse_args(arguments)
    if sys.platform == "win32":
        parser.error("Windows 数据请使用 snapshot --snapshot <目录>；Mac 工作流不能在 Windows 自动运行")
    args.func(args)
    return None


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
