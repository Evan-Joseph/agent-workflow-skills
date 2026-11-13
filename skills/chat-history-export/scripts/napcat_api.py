#!/usr/bin/env python3
import argparse
import http.client
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_BASE_URL = os.environ.get("NAPCAT_BASE_URL", ("http://" + os.environ.get("NAPCAT_HOST", "localhost") + ":" + os.environ.get("NAPCAT_PORT", "3000")))
DEFAULT_TOKEN = os.environ.get("NAPCAT_TOKEN", "")
DEFAULT_QCE_URL = os.environ.get("QCE_BASE_URL", ("http://" + os.environ.get("QCE_HOST", "localhost") + ":" + os.environ.get("QCE_PORT", "40653")))
DEFAULT_QCE_TOKEN = os.environ.get("QCE_TOKEN", "")
DEFAULT_QCE_CONTAINER = os.environ.get("QCE_CONTAINER", "napcat-qce")
DEFAULT_NAPCAT_CONTAINER = os.environ.get("NAPCAT_CONTAINER", DEFAULT_QCE_CONTAINER)
READ_ONLY_ACTIONS = {
    "get_status",
    "get_login_info",
    "get_friend_list",
    "get_friends_with_category",
    "get_group_list",
    "get_group_info",
    "get_group_member_list",
    "get_group_member_info",
    "get_group_root_files",
    "get_group_files_by_folder",
    "get_group_file_url",
}


def redact_secret(text):
    for key in ("access_token=", "token="):
        start = 0
        while key in text[start:]:
            prefix, _, rest = text[start:].partition(key)
            token_value = rest.split("&", 1)
            token_tail = token_value[1] if len(token_value) > 1 else ""
            value = token_value[0]
            stop_chars = ['"', "'", "<", ">", " ", "\n", "\r"]
            cut = len(value)
            for ch in stop_chars:
                pos = value.find(ch)
                if pos != -1:
                    cut = min(cut, pos)
            replacement = key + "***" + value[cut:]
            text = text[:start] + prefix + replacement + (("&" + token_tail) if token_tail else "")
            start = len(text[:start] + prefix + replacement)
    return text


def redact_obj(obj):
    if isinstance(obj, dict):
        redacted = {}
        for key, value in obj.items():
            if str(key).lower() in {"token", "access_token", "accesstoken", "authorization", "password", "secret"}:
                redacted[key] = "***"
            else:
                redacted[key] = redact_obj(value)
        return redacted
    if isinstance(obj, list):
        return [redact_obj(item) for item in obj]
    if isinstance(obj, str):
        return redact_secret(obj)
    return obj


def json_arg(text, default=None):
    if not text:
        return default if default is not None else {}
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON payload: {exc}") from exc


def request_action(base_url, token, action, payload, raw=False, timeout=30):
    base_url = base_url.rstrip("/")
    url = f"{base_url}/{action}"
    body = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {exc.reason}: {redact_secret(detail)}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot connect to {url}: {exc.reason}") from exc
    except http.client.RemoteDisconnected as exc:
        raise SystemExit(
            f"Remote closed connection for {url}. Check NapCat HTTP host/port, protocol, and access token."
        ) from exc
    except (ConnectionResetError, TimeoutError, socket.timeout) as exc:
        raise SystemExit(f"Cannot connect to {url}: {exc}") from exc

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text

    if raw:
        return data
    if isinstance(data, dict) and "data" in data:
        status = data.get("status")
        retcode = data.get("retcode")
        if status not in (None, "ok") or retcode not in (None, 0):
            return data
        return data["data"]
    return data


def load_qce_token(container=DEFAULT_QCE_CONTAINER):
    if DEFAULT_QCE_TOKEN:
        return DEFAULT_QCE_TOKEN
    try:
        out = subprocess.check_output(
            [
                "docker",
                "exec",
                container,
                "python3",
                "-c",
                "import json; print(json.load(open('/app/.qq-chat-exporter/security.json')).get('accessToken',''))",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except Exception:
        return ""
    return out


def load_onebot_token(container=DEFAULT_NAPCAT_CONTAINER):
    if DEFAULT_TOKEN:
        return DEFAULT_TOKEN
    try:
        out = subprocess.check_output(
            [
                "docker",
                "exec",
                container,
                "python3",
                "-c",
                (
                    "import glob,json;"
                    "paths=glob.glob('/app/napcat/config/onebot11_*.json')+glob.glob('/app/napcat/config/onebot11.json');"
                    "cfg=json.load(open(paths[0]));"
                    "servers=cfg.get('network',{}).get('httpServers',[]);"
                    "print(next((s.get('token','') for s in servers if s.get('enable')), ''))"
                ),
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        ).strip()
    except Exception:
        return ""
    return out


def qce_request(base_url, token, method, path, payload=None, raw=False, timeout=60):
    base_url = base_url.rstrip("/")
    url = f"{base_url}{path}"
    data = None
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} {exc.reason}: {redact_secret(detail)}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Cannot connect to {url}: {exc.reason}") from exc

    try:
        data_obj = json.loads(text)
    except json.JSONDecodeError:
        return text

    if raw:
        return data_obj
    if isinstance(data_obj, dict) and data_obj.get("success") is False:
        raise SystemExit(f"QCE API error: {json.dumps(data_obj.get('error', data_obj), ensure_ascii=False)}")
    if isinstance(data_obj, dict) and "data" in data_obj:
        return data_obj["data"]
    return data_obj


def qce_error_code_from_http_error(exc):
    try:
        detail = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return "", ""
    try:
        data = json.loads(detail)
    except json.JSONDecodeError:
        return "", detail
    code = ""
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            context = error.get("context")
            if isinstance(context, dict):
                code = context.get("code", "") or ""
    return code, detail


def restart_container(container):
    try:
        subprocess.check_call(
            ["docker", "restart", container],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=30,
        )
    except Exception as exc:
        raise SystemExit(f"Failed to restart {container}: {exc}") from exc


def qce_request_with_recover(args, method, path, payload=None):
    token = args.qce_token or load_qce_token(args.qce_container)
    try:
        return qce_request(args.qce_url, token, method, path, payload=payload, raw=args.raw)
    except SystemExit as exc:
        message = str(exc)
        if "INVALID_TOKEN" not in message or getattr(args, "no_recover", False):
            raise
        restart_container(args.qce_container)
        deadline = time.time() + 40
        last_error = message
        while time.time() < deadline:
            time.sleep(1)
            token = args.qce_token or load_qce_token(args.qce_container)
            try:
                qce_request(args.qce_url, token, "GET", "/health", raw=False, timeout=5)
                return qce_request(args.qce_url, token, method, path, payload=payload, raw=args.raw)
            except SystemExit as retry_exc:
                last_error = str(retry_exc)
                if "Cannot connect" in last_error or "INVALID_TOKEN" in last_error:
                    continue
                raise
        raise SystemExit(f"QCE token recovery failed after restarting {args.qce_container}: {last_error}") from exc


def qce_chat_type(value):
    mapping = {
        "friend": 1,
        "private": 1,
        "c2c": 1,
        "group": 2,
        "guild": 4,
        "temp": 100,
    }
    text = str(value).strip().lower()
    if text in mapping:
        return mapping[text]
    try:
        return int(text)
    except ValueError as exc:
        raise SystemExit(f"Unsupported QCE chat type: {value}") from exc


def print_json(obj):
    print(json.dumps(redact_obj(obj), ensure_ascii=False, indent=2))


def pick_file_name(url, fallback):
    parsed = urllib.parse.urlparse(url)
    name = Path(urllib.parse.unquote(parsed.path)).name
    return safe_file_name(name or fallback)


def safe_file_name(name):
    name = Path(name).name.strip()
    cleaned = "".join(ch if ch not in '\\/:*?"<>|' else "_" for ch in name)
    return cleaned or f"napcat-file-{int(time.time())}"


def download_url(url, output_dir, file_name=None, token=""):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / (safe_file_name(file_name) if file_name else pick_file_name(url, f"napcat-file-{int(time.time())}"))
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=120) as resp, target.open("wb") as fh:
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            fh.write(chunk)
    return str(target)


def message_text(message):
    parts = []

    def walk(obj):
        if isinstance(obj, dict):
            for key in ("text", "summary", "fileName", "file_name", "name", "content", "msg"):
                value = obj.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(message)
    return " ".join(parts)


def message_sender(message):
    if not isinstance(message, dict):
        return "unknown"
    for key in ("senderName", "sendMemberName", "peerName", "nick", "nickname", "userName"):
        value = message.get(key)
        if value:
            return str(value)
    for key in ("senderUid", "senderUin", "fromUin", "user_id", "userId"):
        value = message.get(key)
        if value:
            return str(value)
    return "unknown"


def message_kinds(message):
    kinds = []
    elements = message.get("elements") if isinstance(message, dict) else None
    if isinstance(elements, list):
        for element in elements:
            if not isinstance(element, dict):
                continue
            if element.get("picElement"):
                kinds.append("image")
            if element.get("fileElement"):
                kinds.append("file")
            if element.get("videoElement"):
                kinds.append("video")
            if element.get("pttElement"):
                kinds.append("voice")
            text_element = element.get("textElement")
            if isinstance(text_element, dict) and isinstance(text_element.get("content"), str):
                content = text_element["content"].lower()
                if "http://" in content or "https://" in content:
                    kinds.append("link")
    if kinds:
        return sorted(set(kinds))
    text = message_text(message).lower()
    for name, markers in {
        "image": ("image", "pic", "图片", ".jpg", ".png", ".gif", ".webp"),
        "file": ("file", "文件", "fileid", "filename"),
        "video": ("video", "视频", ".mp4", ".mov"),
        "voice": ("voice", "audio", "语音", ".amr", ".silk"),
        "link": ("http://", "https://", "url"),
    }.items():
        if any(marker in text for marker in markers):
            kinds.append(name)
    return kinds or ["text"]


def summarize_messages(data, top_n=10):
    messages = data.get("messages", data) if isinstance(data, dict) else data
    if not isinstance(messages, list):
        raise SystemExit("Message response does not contain a message list")
    senders = {}
    kinds = {}
    text_count = 0
    samples = []
    for msg in messages:
        sender = message_sender(msg)
        senders[sender] = senders.get(sender, 0) + 1
        text = message_text(msg)
        if text:
            text_count += 1
            if len(samples) < 8:
                samples.append({"sender": sender, "text": text[:180]})
        for kind in message_kinds(msg):
            kinds[kind] = kinds.get(kind, 0) + 1
    return {
        "message_count": len(messages),
        "text_message_count": text_count,
        "top_senders": sorted(senders.items(), key=lambda x: x[1], reverse=True)[:top_n],
        "message_kinds": dict(sorted(kinds.items(), key=lambda x: x[1], reverse=True)),
        "samples": samples,
    }


def action_for_command(args):
    if args.command == "status":
        return "get_status", {}
    if args.command == "login-info":
        return "get_login_info", {}
    if args.command == "friends":
        return "get_friend_list", {}
    if args.command == "friends-with-category":
        return "get_friends_with_category", {}
    if args.command == "set-friend-remark":
        return "set_friend_remark", {
            "user_id": str(args.user_id),
            "remark": args.remark,
        }
    if args.command == "set-friend-category":
        uid_val = int(args.user_id) if str(args.user_id).isdigit() else str(args.user_id)
        return args.action_name, {
            "user_id": uid_val,
            "category_id": int(args.category_id),
        }
    if args.command == "groups":
        return "get_group_list", {}
    if args.command == "group-info":
        return "get_group_info", {"group_id": args.group_id}
    if args.command == "group-members":
        return "get_group_member_list", {"group_id": args.group_id}
    if args.command == "group-member":
        return "get_group_member_info", {"group_id": args.group_id, "user_id": args.user_id}
    if args.command == "group-files":
        if args.folder_id:
            return "get_group_files_by_folder", {"group_id": args.group_id, "folder_id": args.folder_id}
        return "get_group_root_files", {"group_id": args.group_id}
    if args.command == "send-group-message":
        return "send_group_msg", {"group_id": args.group_id, "message": args.message}
    if args.command == "send-private-message":
        return "send_private_msg", {"user_id": args.user_id, "message": args.message}
    if args.command == "set-qq-profile":
        payload = {"nickname": args.nickname}
        if args.personal_note:
            payload["personal_note"] = args.personal_note
        if args.sex:
            payload["sex"] = args.sex
        return "set_qq_profile", payload
    if args.command in ("group-file-url", "download-group-file"):
        return "get_group_file_url", {
            "group_id": args.group_id,
            "file_id": args.file_id,
            "busid": args.busid,
        }
    if args.command == "call":
        payload = json_arg(args.payload)
        return args.action, payload
    raise SystemExit(f"Unknown command: {args.command}")


def qce_for_command(args):
    if args.command == "qce-health":
        token = args.qce_token or load_qce_token(args.qce_container)
        return qce_request(args.qce_url, token, "GET", "/health", raw=args.raw)
    if args.command == "qce-system":
        return qce_request_with_recover(args, "GET", "/api/system/status")
    if args.command == "qce-groups":
        return qce_request_with_recover(args, "GET", f"/api/groups?page={args.page}&limit={args.limit}&forceRefresh={str(args.force_refresh).lower()}")
    if args.command == "qce-group-info":
        return qce_request_with_recover(args, "GET", f"/api/groups/{args.group_id}?forceRefresh={str(args.force_refresh).lower()}")
    if args.command == "qce-group-members":
        return qce_request_with_recover(args, "GET", f"/api/groups/{args.group_id}/members?forceRefresh={str(args.force_refresh).lower()}")
    if args.command == "qce-group-files":
        query = urllib.parse.urlencode({
            "folderId": args.folder_id,
            "startIndex": args.start_index,
            "fileCount": args.file_count,
        })
        return qce_request_with_recover(args, "GET", f"/api/groups/{args.group_id}/files?{query}")
    if args.command == "qce-group-file-count":
        return qce_request_with_recover(args, "GET", f"/api/groups/{args.group_id}/files/count")
    if args.command == "qce-group-file-download-url":
        payload = json_arg(args.payload, {"fileId": args.file_id}) if args.payload else {"fileId": args.file_id}
        return qce_request_with_recover(args, "POST", f"/api/groups/{args.group_id}/files/download", payload=payload)
    if args.command == "qce-download-group-file":
        payload = {"fileId": args.file_id}
        result = qce_request_with_recover(args, "POST", f"/api/groups/{args.group_id}/files/download", payload=payload)
        url = result.get("downloadUrl") if isinstance(result, dict) else result
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            print_json(result)
            raise SystemExit("No downloadable URL found in QCE response")
        return {"saved_to": download_url(url, args.output_dir, args.file_name or None)}
    if args.command == "qce-messages-fetch":
        payload = json_arg(args.payload) if args.payload else {
            "peer": {"chatType": qce_chat_type(args.chat_type), "peerUid": str(args.peer_uid)},
            "filter": {
                k: v for k, v in {
                    "startTime": args.start_time,
                    "endTime": args.end_time,
                }.items() if v
            },
            "batchSize": args.batch_size,
            "page": args.page,
            "limit": args.limit,
        }
        return qce_request_with_recover(args, "POST", "/api/messages/fetch", payload=payload)
    if args.command == "qce-messages-summary":
        payload = json_arg(args.payload) if args.payload else {
            "peer": {"chatType": qce_chat_type(args.chat_type), "peerUid": str(args.peer_uid)},
            "filter": {
                k: v for k, v in {
                    "startTime": args.start_time,
                    "endTime": args.end_time,
                }.items() if v
            },
            "batchSize": args.batch_size,
            "page": args.page,
            "limit": args.limit,
        }
        data = qce_request_with_recover(args, "POST", "/api/messages/fetch", payload=payload)
        return summarize_messages(data, args.top_n)
    if args.command == "qce-messages-export":
        options = {}
        if args.output_dir:
            options["outputDir"] = args.output_dir
        if args.use_name_in_file_name:
            options["useNameInFileName"] = True
        if args.use_friendly_file_name:
            options["useFriendlyFileName"] = True
        payload = json_arg(args.payload) if args.payload else {
            "peer": {"chatType": qce_chat_type(args.chat_type), "peerUid": str(args.peer_uid)},
            "format": args.format,
            "filter": {
                k: v for k, v in {
                    "startTime": args.start_time,
                    "endTime": args.end_time,
                }.items() if v
            },
            "options": options,
            "sessionName": args.session_name,
        }
        return qce_request_with_recover(args, "POST", "/api/messages/export", payload=payload)
    raise SystemExit(f"Unknown QCE command: {args.command}")


def add_common(parser):
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    parser.add_argument("--napcat-container", default=DEFAULT_NAPCAT_CONTAINER)
    parser.add_argument("--raw", action="store_true", help="Print full OneBot response instead of unwrapped data")


def add_qce_common(parser):
    parser.add_argument("--qce-url", default=DEFAULT_QCE_URL)
    parser.add_argument("--qce-token", default=DEFAULT_QCE_TOKEN)
    parser.add_argument("--qce-container", default=DEFAULT_QCE_CONTAINER)
    parser.add_argument("--no-recover", action="store_true", help="Do not restart the QCE container on INVALID_TOKEN")
    parser.add_argument("--raw", action="store_true", help="Print full QCE response instead of unwrapped data")


def build_parser():
    common = argparse.ArgumentParser(add_help=False)
    add_common(common)
    qce_common = argparse.ArgumentParser(add_help=False)
    add_qce_common(qce_common)
    parser = argparse.ArgumentParser(
        description="Minimal NapCat OneBot HTTP API client",
        parents=[common],
    )
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("status", "login-info", "friends", "friends-with-category", "groups"):
        sub.add_parser(name, parents=[common])

    p = sub.add_parser(
        "contacts-audit",
        parents=[common],
        help="Read-only QQ contacts governance audit (unremarked friends, category distribution, group count)",
    )
    p.add_argument("--json", dest="as_json", action="store_true", help="Output structured JSON (default)")
    p.add_argument("--format", choices=["json", "markdown"], default="json", help="Output format (json or markdown)")
    p.add_argument("--limit", type=int, default=50, help="Max rows per section when --format markdown")

    p = sub.add_parser(
        "set-friend-remark",
        parents=[common],
        help="Controlled OneBot set_friend_remark (dry-run unless --confirm is passed)",
    )
    p.add_argument("--user-id", required=True, help="Target friend QQ number (uin)")
    p.add_argument("--remark", required=True, help="New remark text (empty string clears remark)")
    p.add_argument(
        "--confirm",
        "--confirm-action",
        dest="confirm",
        action="store_true",
        help="Explicitly authorize sending the HTTP mutation; omit for dry-run preview",
    )

    p = sub.add_parser(
        "set-friend-category",
        parents=[common],
        help="Controlled OneBot set_friend_category (dry-run unless --confirm is passed)",
    )
    p.add_argument("--user-id", required=True, help="Target friend QQ number (uin)")
    p.add_argument("--category-id", type=int, required=True, help="Target friend category ID")
    p.add_argument(
        "--action-name",
        default="set_friend_category",
        help="OneBot action endpoint name (default: set_friend_category)",
    )
    p.add_argument(
        "--confirm",
        "--confirm-action",
        dest="confirm",
        action="store_true",
        help="Explicitly authorize sending the HTTP mutation; omit for dry-run preview",
    )

    p = sub.add_parser("group-info", parents=[common])
    p.add_argument("--group-id", type=int, required=True)

    p = sub.add_parser("group-members", parents=[common])
    p.add_argument("--group-id", type=int, required=True)

    p = sub.add_parser("group-member", parents=[common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--user-id", type=int, required=True)

    p = sub.add_parser("group-files", parents=[common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--folder-id", default="", help="Omit for root files")

    p = sub.add_parser("group-file-url", parents=[common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--file-id", required=True)
    p.add_argument("--busid", type=int, required=True)

    p = sub.add_parser("download-group-file", parents=[common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--file-id", required=True)
    p.add_argument("--busid", type=int, required=True)
    p.add_argument("--output-dir", default=".")
    p.add_argument("--file-name", default="")

    p = sub.add_parser("send-group-message", parents=[common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--confirm-send", action="store_true")

    p = sub.add_parser("send-private-message", parents=[common])
    p.add_argument("--user-id", type=int, required=True)
    p.add_argument("--message", required=True)
    p.add_argument("--confirm-send", action="store_true")

    p = sub.add_parser("set-qq-profile", parents=[common])
    p.add_argument("--nickname", required=True)
    p.add_argument("--personal-note", default="")
    p.add_argument("--sex", default="")
    p.add_argument("--confirm-action", action="store_true", help="Required to mutate QQ profile")

    p = sub.add_parser("call", parents=[common])
    p.add_argument("action")
    p.add_argument("--payload", default="{}")
    p.add_argument("--confirm-action", action="store_true", help="Required for non-read-only OneBot actions")

    sub.add_parser("qce-health", parents=[qce_common])
    sub.add_parser("qce-system", parents=[qce_common])

    p = sub.add_parser("qce-groups", parents=[qce_common])
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--force-refresh", action="store_true")

    p = sub.add_parser("qce-group-info", parents=[qce_common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--force-refresh", action="store_true")

    p = sub.add_parser("qce-group-members", parents=[qce_common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--force-refresh", action="store_true")

    p = sub.add_parser("qce-group-files", parents=[qce_common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--folder-id", default="/")
    p.add_argument("--start-index", type=int, default=0)
    p.add_argument("--file-count", type=int, default=100)

    p = sub.add_parser("qce-group-file-count", parents=[qce_common])
    p.add_argument("--group-id", type=int, required=True)

    p = sub.add_parser("qce-group-file-download-url", parents=[qce_common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--file-id", required=True)
    p.add_argument("--payload", default="", help="Raw JSON payload if QCE requires exact file fields")

    p = sub.add_parser("qce-download-group-file", parents=[qce_common])
    p.add_argument("--group-id", type=int, required=True)
    p.add_argument("--file-id", required=True)
    p.add_argument("--output-dir", default=".")
    p.add_argument("--file-name", default="")

    p = sub.add_parser("qce-messages-fetch", parents=[qce_common])
    p.add_argument("--peer-uid", required=True, help="Group code for group chat, uid for private chat")
    p.add_argument("--chat-type", default="group", help="group/friend/temp/guild or raw NTQQ chatType number")
    p.add_argument("--start-time", default="", help="Unix timestamp or API-supported timestamp string")
    p.add_argument("--end-time", default="")
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--payload", default="", help="Raw JSON payload")

    p = sub.add_parser("qce-messages-summary", parents=[qce_common])
    p.add_argument("--peer-uid", required=True, help="Group code for group chat, uid for private chat")
    p.add_argument("--chat-type", default="group", help="group/friend/temp/guild or raw NTQQ chatType number")
    p.add_argument("--start-time", default="", help="Unix timestamp or API-supported timestamp string")
    p.add_argument("--end-time", default="")
    p.add_argument("--batch-size", type=int, default=5000)
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--payload", default="", help="Raw JSON payload")

    p = sub.add_parser("qce-messages-export", parents=[qce_common])
    p.add_argument("--peer-uid", required=True, help="Group code for group chat, uid for private chat")
    p.add_argument("--chat-type", default="group", help="group/friend/temp/guild or raw NTQQ chatType number")
    p.add_argument("--format", default="JSON", choices=["JSON", "TXT", "HTML", "EXCEL"])
    p.add_argument("--start-time", default="")
    p.add_argument("--end-time", default="")
    p.add_argument("--output-dir", default="")
    p.add_argument("--session-name", default="")
    p.add_argument("--use-name-in-file-name", action="store_true")
    p.add_argument("--use-friendly-file-name", action="store_true")
    p.add_argument("--payload", default="", help="Raw JSON payload")

    return parser


def run_qq_contacts_audit(args):
    token = args.token or load_onebot_token(args.napcat_container)
    categories_raw = None
    category_source = "get_friends_with_category"
    try:
        resp = request_action(args.base_url, token, "get_friends_with_category", {}, raw=False)
        if isinstance(resp, list):
            categories_raw = resp
    except SystemExit:
        categories_raw = None

    flat_friends = []
    categories_summary = []
    seen_uids = set()

    if isinstance(categories_raw, list):
        for cat in categories_raw:
            if not isinstance(cat, dict):
                continue
            cid = cat.get("categoryId")
            cname = str(cat.get("categoryName") or f"分组_{cid}")
            buddies = cat.get("buddyList") or []
            unrem_cnt = 0
            for b in buddies:
                if not isinstance(b, dict):
                    continue
                uid = str(b.get("user_id") or b.get("uin") or "")
                nick = str(b.get("nickname") or b.get("nick") or "").strip()
                remark = str(b.get("remark") or "").strip()
                if not remark:
                    unrem_cnt += 1
                if uid and uid not in seen_uids:
                    seen_uids.add(uid)
                    flat_friends.append({
                        "user_id": uid,
                        "nickname": nick,
                        "remark": remark,
                        "display_name": remark or nick or uid,
                        "category_id": cid,
                        "category_name": cname,
                    })
            categories_summary.append({
                "category_id": cid,
                "category_name": cname,
                "friend_count": len(buddies),
                "unremarked_count": unrem_cnt,
            })
    else:
        category_source = "get_friend_list"
        friends_resp = request_action(args.base_url, token, "get_friend_list", {}, raw=False)
        if not isinstance(friends_resp, list):
            raise SystemExit(f"Unexpected get_friend_list response: {redact_obj(friends_resp)}")
        unrem_cnt = 0
        for b in friends_resp:
            if not isinstance(b, dict):
                continue
            uid = str(b.get("user_id") or b.get("uin") or "")
            nick = str(b.get("nickname") or b.get("nick") or "").strip()
            remark = str(b.get("remark") or "").strip()
            cid = b.get("category_id")
            cname = str(b.get("category_name") or (f"分组_{cid}" if cid is not None else "默认分组"))
            if not remark:
                unrem_cnt += 1
            flat_friends.append({
                "user_id": uid,
                "nickname": nick,
                "remark": remark,
                "display_name": remark or nick or uid,
                "category_id": cid,
                "category_name": cname,
            })
        categories_summary.append({
            "category_id": None,
            "category_name": "全部好友(get_friend_list回退)",
            "friend_count": len(flat_friends),
            "unremarked_count": unrem_cnt,
        })

    groups_resp = []
    try:
        g_res = request_action(args.base_url, token, "get_group_list", {}, raw=False)
        if isinstance(g_res, list):
            groups_resp = g_res
    except SystemExit:
        groups_resp = []

    unremarked = [f for f in flat_friends if not f["remark"]]
    by_name = {}
    for f in flat_friends:
        key = f["display_name"].strip().casefold()
        if key:
            by_name.setdefault(key, []).append(f)
    duplicates = [
        {"display_name": items[0]["display_name"], "count": len(items), "friends": items}
        for _, items in sorted(by_name.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        if len(items) >= 2
    ]

    return {
        "source": {
            "base_url": args.base_url,
            "category_action": category_source,
            "read_only": True,
        },
        "summary": {
            "total_friends": len(flat_friends),
            "remarked_friends": len(flat_friends) - len(unremarked),
            "unremarked_friends": len(unremarked),
            "category_count": len(categories_summary),
            "duplicate_name_groups": len(duplicates),
            "total_groups": len(groups_resp),
        },
        "categories": categories_summary,
        "unremarked_friends": unremarked,
        "duplicate_names": duplicates,
    }


def render_qq_contacts_audit_markdown(audit, limit=50):
    s = audit["summary"]
    lines = [
        "# QQ (NapCat/OneBot) 联系人只读治理审计摘要",
        "",
        f"- 接口来源：`{audit['source']['base_url']}`（`{audit['source']['category_action']}`，只读）",
        f"- 好友总数：**{s['total_friends']}**（已备注 **{s['remarked_friends']}** / 无备注 **{s['unremarked_friends']}**）",
        f"- 分组总数：**{s['category_count']}** ｜ 群聊总数：**{s['total_groups']}** ｜ 重名好友组：**{s['duplicate_name_groups']}**",
        "",
        "## 1. 分组分布",
        "",
        "| 分组 ID | 分组名称 | 好友数 | 无备注数 |",
        "| :---: | :--- | :---: | :---: |",
    ]
    for c in audit["categories"]:
        cid = "-" if c["category_id"] is None else str(c["category_id"])
        lines.append(f"| {cid} | {c['category_name']} | {c['friend_count']} | {c['unremarked_count']} |")
    unrem = audit["unremarked_friends"]
    shown = unrem if limit <= 0 else unrem[:limit]
    lines.extend([
        "",
        f"## 2. 无备注好友名单（共 {len(unrem)} 人，展示前 {len(shown)} 人）",
        "",
    ])
    if shown:
        lines.extend([
            "| # | QQ 号 | 昵称 | 所属分组 |",
            "| :---: | :--- | :--- | :--- |",
        ])
        for idx, item in enumerate(shown, 1):
            lines.append(f"| {idx} | `{item['user_id']}` | {item['nickname'] or '-'} | {item['category_name']} |")
    else:
        lines.append("全部 QQ 好友均已设置备注。")
    return "\n".join(lines)


def main():
    args = build_parser().parse_args()
    if args.command.startswith("qce-"):
        print_json(qce_for_command(args))
        return

    if args.command == "contacts-audit":
        audit = run_qq_contacts_audit(args)
        if getattr(args, "format", "json") == "markdown" and not getattr(args, "as_json", False):
            print(render_qq_contacts_audit_markdown(audit, limit=args.limit))
        else:
            print_json(audit)
        return

    action, payload = action_for_command(args)
    if args.command in ("set-friend-remark", "set-friend-category") and not args.confirm:
        print_json({
            "action": action,
            "payload": payload,
            "dry_run": True,
            "hint": "Dry-run preview only. Pass --confirm to execute HTTP Action.",
        })
        return
    if args.command in ("send-group-message", "send-private-message") and not args.confirm_send:
        print_json({"action": action, "payload": payload, "dry_run": True})
        raise SystemExit("Refusing to send without --confirm-send")
    if args.command == "set-qq-profile" and not args.confirm_action:
        print_json({"action": action, "payload": payload, "dry_run": True})
        raise SystemExit("Refusing to change QQ profile without --confirm-action")
    if args.command == "call" and action not in READ_ONLY_ACTIONS and not args.confirm_action:
        print_json({"action": action, "payload": payload, "dry_run": True})
        raise SystemExit("Refusing non-read-only OneBot action without --confirm-action")
    token = args.token or load_onebot_token(args.napcat_container)
    result = request_action(args.base_url, token, action, payload, raw=args.raw)

    if args.command == "download-group-file":
        url = result.get("url") if isinstance(result, dict) else result
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            print_json(result)
            raise SystemExit("No downloadable URL found in response")
        path = download_url(url, args.output_dir, args.file_name or None)
        print(path)
        return

    print_json(result)


if __name__ == "__main__":
    main()
