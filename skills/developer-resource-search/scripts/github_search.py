#!/usr/bin/env python3
"""GitHub 搜索：仓库、代码、Issue、Commit、Release。通过 GitHub REST API。"""
from __future__ import annotations

import re
import sys

from search_utils import build_parser, get_client, get_github_token, make_item, make_result, print_json


API_ROOT = "https://api.github.com"
API_BASE = f"{API_ROOT}/search"
OWNER_REPO_RE = re.compile(r"^(?:repo:)?([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)$")

# 搜索类型 -> 规范类型
SEARCH_TYPES = {
    "repositories": "repositories",
    "repos": "repositories",
    "repo": "repositories",
    "code": "code",
    "issues": "issues",
    "issue": "issues",
    "commits": "commits",
    "commit": "commits",
    "releases": "releases",
    "release": "releases",
}

SORT_CHOICES = ("best-match", "stars", "updated")


def _truncate(text: str, max_len: int) -> str:
    return text[:max_len] + "..." if len(text) > max_len else text


def _headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _map_sort(endpoint: str, sort: str) -> str | None:
    if sort == "best-match":
        return None
    if endpoint == "repositories":
        return sort  # "stars" | "updated"
    if endpoint == "issues":
        return "reactions" if sort == "stars" else "updated"
    if endpoint == "commits":
        return "committer-date" if sort == "updated" else None
    if endpoint == "code":
        return "indexed" if sort == "updated" else None
    return None


def _search_releases(query: str, limit: int, sort: str, token: str | None) -> list[dict]:
    headers = _headers(token)
    m = OWNER_REPO_RE.match(query.strip())
    items: list[dict] = []
    with get_client(headers=headers) as client:
        if m:
            full_name = m.group(1)
            resp = client.get(
                f"{API_ROOT}/repos/{full_name}/releases",
                params={"per_page": min(max(1, limit), 100)},
            )
            resp.raise_for_status()
            for rel in (resp.json() or [])[:limit]:
                tag = rel.get("tag_name") or ""
                name = rel.get("name") or tag
                items.append(make_item(
                    title=f"{full_name} {tag}" + (f" — {name}" if name and name != tag else ""),
                    url=rel.get("html_url", ""),
                    snippet=_truncate((rel.get("body") or "").strip(), 240),
                    repo=full_name,
                    tag_name=tag,
                    prerelease=rel.get("prerelease", False),
                    published_at=rel.get("published_at") or rel.get("created_at"),
                ))
            return items

        repo_params: dict[str, str | int] = {"q": query, "per_page": min(max(limit, 5), 15)}
        mapped = _map_sort("repositories", sort)
        if mapped:
            repo_params["sort"] = mapped
        resp = client.get(f"{API_BASE}/repositories", params=repo_params)
        resp.raise_for_status()
        repos = (resp.json() or {}).get("items", [])
        for repo in repos:
            if len(items) >= limit:
                break
            full_name = repo.get("full_name")
            if not full_name:
                continue
            r_resp = client.get(f"{API_ROOT}/repos/{full_name}/releases", params={"per_page": 1})
            if r_resp.status_code != 200:
                continue
            rels = r_resp.json() or []
            if not rels:
                continue
            rel = rels[0]
            tag = rel.get("tag_name") or ""
            name = rel.get("name") or tag
            items.append(make_item(
                title=f"{full_name} {tag}" + (f" — {name}" if name and name != tag else ""),
                url=rel.get("html_url", ""),
                snippet=_truncate((rel.get("body") or repo.get("description") or "").strip(), 240),
                repo=full_name,
                tag_name=tag,
                stars=repo.get("stargazers_count", 0),
                published_at=rel.get("published_at") or rel.get("created_at"),
            ))
    return items


def search(
    query: str,
    limit: int,
    search_type: str = "repositories",
    token: str | None = None,
    sort: str = "best-match",
) -> list[dict]:
    """执行 GitHub 搜索。"""
    endpoint = SEARCH_TYPES.get(search_type, "repositories")
    if endpoint == "releases":
        return _search_releases(query, limit, sort, token)

    headers = _headers(token)
    if endpoint == "commits":
        m = OWNER_REPO_RE.match(query.strip())
        if m:
            full_name = m.group(1)
            with get_client(headers=headers) as client:
                resp = client.get(
                    f"{API_ROOT}/repos/{full_name}/commits",
                    params={"per_page": min(max(1, limit), 100)},
                )
                resp.raise_for_status()
                raw_commits = resp.json() or []
            items = []
            for c in raw_commits[:limit]:
                commit_obj = c.get("commit") or {}
                msg = (commit_obj.get("message") or "").splitlines()[0]
                author_info = commit_obj.get("author") or {}
                items.append(make_item(
                    title=f"{full_name}@{str(c.get('sha') or '')[:8]}: {msg}",
                    url=c.get("html_url", ""),
                    snippet=_truncate(commit_obj.get("message") or "", 220),
                    repo=full_name,
                    sha=c.get("sha"),
                    author=author_info.get("name"),
                    date=author_info.get("date"),
                ))
            return items

    url = f"{API_BASE}/{endpoint}"
    params: dict[str, str | int] = {
        "q": query,
        "per_page": min(limit, 100),
    }
    mapped_sort = _map_sort(endpoint, sort)
    if mapped_sort:
        params["sort"] = mapped_sort
        params["order"] = "desc"

    with get_client(headers=headers) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    items = []
    for item in data.get("items", [])[:limit]:
        if endpoint == "repositories":
            items.append(make_item(
                title=item.get("full_name", ""),
                url=item.get("html_url", ""),
                snippet=item.get("description") or "",
                stars=item.get("stargazers_count", 0),
                language=item.get("language"),
                updated_at=item.get("updated_at"),
            ))
        elif endpoint == "code":
            repo = item.get("repository", {})
            items.append(make_item(
                title=item.get("name", ""),
                url=item.get("html_url", ""),
                snippet=f"{repo.get('full_name', '')} - {item.get('path', '')}",
                repo=repo.get("full_name"),
                path=item.get("path"),
            ))
        elif endpoint == "issues":
            items.append(make_item(
                title=item.get("title", ""),
                url=item.get("html_url", ""),
                snippet=_truncate(item.get("body") or "", 200),
                state=item.get("state"),
                comments=item.get("comments", 0),
                created_at=item.get("created_at"),
            ))
        elif endpoint == "commits":
            repo = item.get("repository", {})
            commit_obj = item.get("commit") or {}
            msg = (commit_obj.get("message") or "").splitlines()[0]
            author_info = commit_obj.get("author") or {}
            full_name = repo.get("full_name", "")
            items.append(make_item(
                title=f"{full_name}@{str(item.get('sha') or '')[:8]}: {msg}",
                url=item.get("html_url", ""),
                snippet=_truncate(commit_obj.get("message") or "", 220),
                repo=full_name,
                sha=item.get("sha"),
                author=author_info.get("name"),
                date=author_info.get("date"),
            ))
    return items


def main():
    parser = build_parser("搜索 GitHub 仓库、代码、Issue、Commit、Release")
    parser.add_argument("--type", "-t", default="repositories",
                        choices=list(SEARCH_TYPES.keys()),
                        help="搜索类型（默认 repositories，支持 releases / commits）")
    parser.add_argument("--sort", "-s", default="best-match",
                        choices=list(SORT_CHOICES),
                        help="排序方式：best-match（默认）、stars、updated")
    parser.add_argument("--token", help="GitHub Token（也可通过 GITHUB_TOKEN/GH_TOKEN 或 gh auth token 设置）")
    args = parser.parse_args()

    token = get_github_token(args.token)
    try:
        items = search(args.query, args.limit, args.type, token, sort=args.sort)
        print_json(make_result(True, args.query, "github", items))
    except Exception as e:
        print_json(make_result(False, args.query, "github", [], str(e)))
        sys.exit(1)


if __name__ == "__main__":
    main()
