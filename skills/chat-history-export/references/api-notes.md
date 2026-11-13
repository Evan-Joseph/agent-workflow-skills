# NapCat / OneBot API Notes

NapCat exposes OneBot-compatible actions over HTTP. The exact port and token depend on the local NapCat config.

## Current Local Setup

Observed on this Mac:

- Docker container: `napcat-qce`
- NapCat WebUI: `${NAPCAT_WEBUI_URL}/webui`
- QCE plugin API: `${QCE_BASE_URL}`
- Standard OneBot HTTP is currently disabled in `onebot11_2830637620.json` because `network.httpServers` is empty.
- QCE token is stored inside the container at `/app/.qq-chat-exporter/security.json`; do not print it in final answers.

## Transport

Most actions are POST requests to:

```text
{base_url}/{action}
```

Example:

```bash
curl -s -X POST ${NAPCAT_BASE_URL}/get_group_info \
  -H 'Content-Type: application/json' \
  -d '{"group_id":123456789}'
```

When an access token is configured, use:

```text
Authorization: Bearer <token>
```

Some deployments also accept `access_token=<token>` as a query parameter, but the header is preferred.

## Common Read-Only Actions

| Purpose | Action | Typical Payload |
|---|---|---|
| NapCat/OneBot status | `get_status` | `{}` |
| Current QQ login | `get_login_info` | `{}` |
| Friend list | `get_friend_list` | `{}` |
| Friend list with categories | `get_friends_with_category` | `{}` |
| Group list | `get_group_list` | `{}` |
| Group info | `get_group_info` | `{"group_id":123}` |
| Group member list | `get_group_member_list` | `{"group_id":123}` |
| One group member | `get_group_member_info` | `{"group_id":123,"user_id":456}` |
| Root group files | `get_group_root_files` | `{"group_id":123}` |
| Folder files | `get_group_files_by_folder` | `{"group_id":123,"folder_id":"..."}` |
| Group file URL | `get_group_file_url` | `{"group_id":123,"file_id":"...","busid":...}` |

## QCE Plugin Read-Only Endpoints

The user's current NapCat container includes `qq-chat-exporter`, which exposes a separate REST API:

| Purpose | Endpoint |
|---|---|
| Health | `GET /health` |
| System status | `GET /api/system/status` |
| Group list | `GET /api/groups?page=1&limit=999&forceRefresh=false` |
| Group detail | `GET /api/groups/:groupCode?forceRefresh=false` |
| Group members | `GET /api/groups/:groupCode/members?forceRefresh=false` |
| Group files | `GET /api/groups/:groupCode/files` |
| Group file count | `GET /api/groups/:groupCode/files/count` |
| Single file download link | `POST /api/groups/:groupCode/files/download` |
| Export group file list | `POST /api/groups/:groupCode/files/export` |
| Export group files with downloads | `POST /api/groups/:groupCode/files/export-with-download` |
| Fetch messages | `POST /api/messages/fetch` |
| Export messages | `POST /api/messages/export` |

QCE requires its own access token. The bundled script auto-reads it from the local `napcat-qce` container when possible, but final answers must not expose the token.

`GET /api/groups/:groupCode/files` supports query parameters:

- `folderId`, default `/`
- `startIndex`, default `0`
- `fileCount`, default `100`

`POST /api/messages/fetch` minimum payload:

```json
{
  "peer": {"chatType": "group", "peerUid": "123456789"},
  "page": 1,
  "limit": 50
}
```

`POST /api/messages/export` minimum payload:

```json
{
  "peer": {"chatType": "group", "peerUid": "123456789"},
  "format": "HTML",
  "options": {"outputDir": "./qq-export"}
}
```

## Sending Through Standard OneBot

The helper supports only text sending helpers by default:

```bash
python3 scripts/napcat_api.py send-group-message --group-id 123 --message "text"
python3 scripts/napcat_api.py send-group-message --group-id 123 --message "text" --confirm-send
```

Without `--confirm-send`, the command prints a dry-run payload and exits.

Friend remark and category mutations are wrapped by dedicated controlled subcommands (`set-friend-remark` and `set-friend-category`), which print a dry-run preview unless `--confirm` is explicitly passed:

```bash
python3 scripts/napcat_api.py contacts-audit --format markdown
python3 scripts/napcat_api.py set-friend-remark --user-id 123456 --remark "姓名-单位"
python3 scripts/napcat_api.py set-friend-remark --user-id 123456 --remark "姓名-单位" --confirm
python3 scripts/napcat_api.py set-friend-category --user-id 123456 --category-id 1 --confirm
```

Other mutating actions should go through `call --confirm-action` only after the user explicitly authorizes the exact action.

## Response Shape

OneBot responses usually look like:

```json
{
  "status": "ok",
  "retcode": 0,
  "data": {}
}
```

The script unwraps `data` by default for display. If debugging, use `--raw`.

## Group File Fields

Group file list responses commonly contain arrays named `files` and `folders`.

Files usually include:

- `file_id`
- `file_name`
- `busid`
- `file_size`
- `upload_time`
- `dead_time`
- `download_times`
- uploader fields such as `uploader` or `uploader_name`

Folders usually include:

- `folder_id`
- `folder_name`
- `create_time`
- creator fields

For standard OneBot, use both `file_id` and `busid` when requesting a download URL.

For QCE, `POST /api/groups/:groupCode/files/download` requires only `fileId`.

## Raw Curl Fallback

```bash
BASE=${NAPCAT_BASE_URL}
TOKEN=
curl -s -X POST "$BASE/get_group_list" \
  -H "Content-Type: application/json" \
  ${TOKEN:+-H "Authorization: Bearer $TOKEN"} \
  -d '{}'
```
