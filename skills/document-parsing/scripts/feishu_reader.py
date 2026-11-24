#!/usr/bin/env python3
"""Feishu/Lark Docx, Canvas Sheet & Bitable 3-mode reader.

Ported from AmbroseX/larksnap (`main` 26d0e510db7269478fb0e8947792dc79db306f38) and
local verified implementation:
1. Docx/tables (`/docx/`): pure HTTP cookie + `/space/api/docx/pages/client_vars` (`mode=1` + `mode=4` skip_blocks).
2. Canvas Sheets (`/sheets/`, `/wiki/?sheet=`): `:9223` `cdp-ctl` reading `window.spreadApp` / `window.spread`.
3. Bitable (`/base/`, `/wiki/?table=`): `:9223` `cdp-ctl` reading `window.bitableStore` with `cellValueToString` /
   `cellValueToStdValue` and explicit partial-load reporting (`loaded < total`).

All `:9223` browser paths enforce `try/finally` `cdp-ctl cleanup --task feishu-reader` for zero leftover tabs.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any
import urllib.parse
import urllib.request

CDP_CTL = ["python3", "cdp-ctl"]
CDP_TASK = "feishu-reader"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36"

JS_EXTRACT_FEISHU_PAGE = r"""((opts) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const quiet = (fn) => { try { return fn(); } catch { return null; } };
  const arr = (o) => (Array.isArray(o) ? o : o && typeof o === 'object' ? Object.values(o) : []);
  const cleanTitle = (raw) => String(raw || '')
    .replace(/[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]/g, '')
    .replace(/\s+[-–—]\s+.*$/, '')
    .trim();

  const listWindows = () => {
    const wins = [window];
    for (const f of document.querySelectorAll('iframe')) {
      try {
        const cw = f.contentWindow;
        if (cw && cw.location && cw.location.href !== undefined) wins.push(cw);
      } catch {}
    }
    return wins;
  };

  const findSpread = () => {
    for (const w of listWindows()) {
      const hit = quiet(() => {
        const app = w.spreadApp || null;
        const spread = (app && quiet(() => app.shell.viewModelManager.spread)) || w.spread || null;
        return (spread && spread.sheets && spread.sheets.length) ? { app, spread } : null;
      });
      if (hit) return hit;
    }
    return null;
  };

  const findBitable = () => {
    for (const w of listWindows()) {
      const hit = quiet(() => {
        const store = w.bitableStore || null;
        if (!store) return null;
        const svc = arr(store.services).find((x) => x && x.modelOperator && x.modelOperator.base);
        return (svc && svc.modelOperator && svc.modelOperator.base)
          ? { store, svc, base: svc.modelOperator.base }
          : null;
      });
      if (hit) return hit;
    }
    return null;
  };

  const clickTab = (name) => {
    const cont = document.querySelector('.sheet-tabs') || document;
    const el = [...cont.querySelectorAll('.tab-name')].find((e) => e.textContent?.trim() === name)
      || [...cont.querySelectorAll('*')].find((e) => e.children.length === 0 && e.textContent?.trim() === name);
    if (!el) return false;
    const rc = el.getBoundingClientRect();
    const xy = { clientX: rc.x + rc.width / 2, clientY: rc.y + rc.height / 2, bubbles: true, cancelable: true, view: window };
    for (const [Type, ev] of [
      [PointerEvent, 'pointerdown'],
      [MouseEvent, 'mousedown'],
      [PointerEvent, 'pointerup'],
      [MouseEvent, 'mouseup'],
      [MouseEvent, 'click'],
    ]) {
      el.dispatchEvent(new Type(ev, Type === PointerEvent ? { ...xy, pointerId: 1, isPrimary: true } : xy));
    }
    return true;
  };

  const readGrid = (s, maxR, maxC) => {
    const R = Math.min(s.getRowCount(), maxR), C = Math.min(s.getColumnCount(), maxC);
    const g = [];
    let lr = -1, lc = -1;
    for (let r = 0; r < R; r++) {
      const row = [];
      for (let c = 0; c < C; c++) {
        let v = quiet(() => s.getText(r, c));
        v = v == null ? '' : String(v).trim();
        if (v !== '') { if (r > lr) lr = r; if (c > lc) lc = c; }
        row.push(v);
      }
      g.push(row);
    }
    return lr < 0 ? [] : g.slice(0, lr + 1).map((row) => row.slice(0, lc + 1));
  };

  const cellToStr = (field, cell) => {
    if (!cell || cell.value == null) return '';
    try {
      if (typeof field.cellValueToString === 'function') {
        const s = field.cellValueToString(cell.value);
        if (s != null) return String(s);
      }
    } catch {}
    try {
      const std = field.cellValueToStdValue(cell.value);
      const d = (std && std.data) || [];
      return d.map((x) => (x && x.text != null ? x.text : '')).join(', ').trim();
    } catch {
      return '';
    }
  };

  const readBitable = (base, maxR, maxC) => {
    try {
      const tables = [];
      for (const block of arr(base.blocks)) {
        const fieldList = arr(block.fields);
        if (fieldList.length === 0) continue;
        const fieldsById = {};
        for (const f of fieldList) fieldsById[f.id] = f;
        const views = arr(block.views);
        const grid = views.find((v) => v.type === 1) || views[0];
        const orderIds = (grid && grid._visibleFieldIds && grid._visibleFieldIds.length)
          ? Array.from(grid._visibleFieldIds)
          : Object.keys(fieldsById);
        const cols = orderIds.map((id) => fieldsById[id]).filter(Boolean).slice(0, maxC);
        if (cols.length === 0) continue;
        const records = block.records || {};
        const recIds = Object.keys(records);
        const limitIds = recIds.slice(0, maxR);
        const rows = [cols.map((f) => String(f.name ?? ''))];
        for (const rid of limitIds) {
          const rec = records[rid] || {};
          rows.push(cols.map((f) => cellToStr(f, rec[f.id])));
        }
        tables.push({
          id: String(block.id ?? ''),
          name: String(block.name ?? ''),
          rows,
          loaded: limitIds.length,
          total: Number(block.recordsNum ?? recIds.length),
        });
      }
      const titleEl = document.querySelector('[data-testid="wiki-title"], .wiki-header-title, .suite-title');
      const title = cleanTitle(titleEl?.textContent || document.title);
      return { ok: true, mode: 'bitable', title, tables };
    } catch (err) {
      return { ok: false, error: 'readBitable failed: ' + (err?.message || String(err)) };
    }
  };

  return (async () => {
    try {
      let sheetCtx = null;
      let bitableCtx = null;
      for (let i = 0; i < 20; i++) {
        if (opts.mode !== 'bitable') sheetCtx = findSpread();
        if (opts.mode !== 'sheet') bitableCtx = findBitable();
        if (opts.prefer === 'bitable' && bitableCtx) break;
        if (opts.prefer !== 'bitable' && sheetCtx) break;
        if (opts.mode === 'auto' && (sheetCtx || bitableCtx) && i >= 2) break;
        await sleep(700);
      }

      if ((opts.prefer === 'bitable' && bitableCtx) || (opts.mode !== 'sheet' && bitableCtx && !sheetCtx)) {
        return JSON.stringify(readBitable(bitableCtx.base, opts.maxRows, opts.maxCols));
      }

      if (sheetCtx) {
        const { app, spread } = sheetCtx;
        const getActive = () => (app && quiet(() => app.collaborativeSpread.getActiveSheet())) || quiet(() => spread.getActiveSheet());
        const meta = Array.from(spread.sheets).map((s) => ({ id: String(s.id()), name: String(s.name()) }));
        let targets = meta;
        if (!opts.allSheets) {
          const cur = getActive();
          const hit = opts.sheet
            ? meta.find((m) => m.id === opts.sheet || m.name === opts.sheet)
            : (cur ? { id: String(cur.id()), name: String(cur.name()) } : meta[0]);
          targets = hit ? [hit] : [];
        }
        const sheets = [];
        for (const t of targets) {
          const cur = getActive();
          if (!cur || String(cur.name()) !== t.name) clickTab(t.name);
          let rows = [];
          for (let i = 0; i < 12; i++) {
            const s = getActive();
            if (s && String(s.name()) === t.name) {
              rows = readGrid(s, opts.maxRows, opts.maxCols);
              if (rows.length > 0 || i >= 4) break;
            }
            await sleep(600);
          }
          sheets.push({ id: t.id, name: t.name, rows });
        }
        const titleEl = document.querySelector('[data-testid="wiki-title"], .wiki-header-title, .suite-title');
        const title = cleanTitle(titleEl?.textContent || document.title);
        return JSON.stringify({ ok: true, mode: 'canvas_sheet', title, sheets });
      }

      let globals = '';
      try {
        globals = Object.keys(window).filter((k) => /spread|bitable|base|table|grid/i.test(k)).slice(0, 20).join(', ');
      } catch {}
      return JSON.stringify({
        ok: false,
        error: `spreadApp/spread/bitableStore not found (mode=${opts.mode}; globals=${globals || 'none'})`,
      });
    } catch (err) {
      return JSON.stringify({ ok: false, error: 'feishu extractor exception: ' + (err?.message || String(err)) });
    }
  })();
})"""


def classify_url_mode(url: str, requested_mode: str = "auto") -> str:
    if requested_mode != "auto":
        return requested_mode
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or ""
    qs = urllib.parse.parse_qs(parsed.query)
    if "/docx/" in path:
        return "docx"
    if "/base/" in path or ("table" in qs and "sheet" not in qs):
        return "bitable"
    if "/sheets/" in path or "sheet" in qs:
        return "sheet"
    return "auto"


def parse_docx_client_vars(token: str, data: dict[str, Any], bmap: dict[str, Any]) -> dict[str, Any]:
    def blk_text(bid: str) -> list[str]:
        bd = (bmap.get(bid) or {}).get("data") or {}
        out: list[str] = []
        iat = bd.get("text", {}).get("initialAttributedTexts", {}).get("text", {})
        if isinstance(iat, dict):
            s = "".join(str(v) for v in iat.values()).strip()
            if s:
                out.append(s)
        for ch in bd.get("children", []):
            out.extend(blk_text(ch))
        return out

    lines, tables, seen = [], [], set()
    for bid in (data.get("block_sequence") or list(bmap.keys())):
        td = (bmap.get(bid) or {}).get("data") or {}
        if "rows_id" in td and "columns_id" in td and bid not in seen:
            seen.add(bid)
            cset = td.get("cell_set") or {}
            tables.append({
                "block_id": bid,
                "rows": [
                    [" / ".join(blk_text(cset.get(f"{rid}{cid}", {}).get("block_id", ""))) for cid in td["columns_id"]]
                    for rid in td["rows_id"]
                ],
            })
        else:
            iat = td.get("text", {}).get("initialAttributedTexts", {}).get("text", {})
            if isinstance(iat, dict):
                s = "".join(str(v) for v in iat.values()).strip()
                if s:
                    lines.append(s)
    return {"ok": True, "mode": "docx_client_vars", "token": token, "lines": lines, "tables": tables}


def fetch_docx_via_http(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    m = re.search(r"/docx/([A-Za-z0-9]+)", parsed.path)
    if not m:
        return {"ok": False, "error": "Unsupported URL for HTTP docx mode"}
    token = m.group(1)
    base = f"{parsed.scheme}://{parsed.netloc}"
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    opener.addheaders = [("User-Agent", UA)]
    with opener.open(url, timeout=15) as _:
        pass

    def get_vars(q: str) -> dict[str, Any]:
        with opener.open(f"{base}/space/api/docx/pages/client_vars?{q}", timeout=15) as r:
            return json.loads(r.read().decode("utf-8", errors="replace")).get("data", {})

    data = get_vars(f"id={token}&mode=1&limit=239")
    bmap: dict[str, Any] = dict(data.get("block_map") or {})
    for sbid in data.get("skip_blocks") or []:
        bmap.update(get_vars(f"id={token}&mode=4&block_id={urllib.parse.quote(str(sbid))}&limit=239").get("block_map") or {})
    return parse_docx_client_vars(token, data, bmap)


def fetch_cdp_page(
    url: str,
    *,
    mode: str,
    prefer: str,
    sheet: str | None,
    all_sheets: bool,
    max_rows: int,
    max_cols: int,
) -> dict[str, Any]:
    def cdp(*args: str) -> tuple[int, str]:
        res = subprocess.run(CDP_CTL + list(args), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=40)
        return res.returncode, res.stdout.strip()

    payload = {
        "mode": mode,
        "prefer": prefer,
        "sheet": sheet,
        "allSheets": all_sheets,
        "maxRows": max_rows,
        "maxCols": max_cols,
    }
    expr = f"({JS_EXTRACT_FEISHU_PAGE})({json.dumps(payload)})"
    try:
        rc, out = cdp("open", "--url", url, "--task", CDP_TASK, "--group", "飞书表格读取", "--reuse", "--resident")
        if rc != 0:
            return {"ok": False, "error": f"cdp open failed: {out[:200]}"}
        time.sleep(2.5)
        rc_e, eval_out = cdp("eval", "--task", CDP_TASK, "--expression", expr)
        if rc_e != 0:
            return {"ok": False, "error": f"cdp eval failed: {eval_out[:200]}"}
        val = json.loads(eval_out).get("result", {}).get("result", {}).get("value")
        return json.loads(val) if isinstance(val, str) else {"ok": False, "error": f"unexpected eval value: {val}"}
    finally:
        cdp("cleanup", "--task", CDP_TASK)


def format_markdown(data: dict[str, Any]) -> str:
    if not data.get("ok"):
        return f"ERROR: {data.get('error')}"
    mode = data.get("mode")
    if mode == "docx_client_vars":
        parts = [f"# Docx {data.get('token')}", "", *data.get("lines", [])]
        for idx, tbl in enumerate(data.get("tables", []), 1):
            parts.extend(["", f"## Table {idx}", *(" | ".join(r) for r in tbl["rows"])])
        return "\n".join(parts)
    if mode == "bitable":
        parts = [f"# {data.get('title') or 'Feishu Bitable'}"]
        for tb in data.get("tables", []):
            loaded = int(tb.get("loaded", 0))
            total = int(tb.get("total", loaded))
            note = f" [PARTIAL: loaded {loaded}/{total} rows]" if loaded < total else f" ({loaded}/{total} rows)"
            parts.extend(["", f"## {tb.get('name') or tb.get('id')}{note}"])
            parts.extend(" | ".join(str(c).replace("\n", "; ") for c in r) for r in tb.get("rows", []))
        return "\n".join(parts)
    parts = [f"# {data.get('title') or 'Feishu Sheet'}"]
    for sh in data.get("sheets", []):
        parts.extend(["", f"## {sh['name']} ({sh['id']})", *(" | ".join(c.replace("\n", "; ") for c in r) for r in sh["rows"])])
    return "\n".join(parts)


def run_self_test() -> int:
    assert classify_url_mode("https://bytedance.larkoffice.com/docx/AbCdEf123") == "docx"
    assert classify_url_mode("https://bytedance.larkoffice.com/sheets/ShEeT123") == "sheet"
    assert classify_url_mode("https://bytedance.larkoffice.com/wiki/Wiki123?sheet=s1") == "sheet"
    assert classify_url_mode("https://bytedance.larkoffice.com/base/Base123?table=tbl1") == "bitable"
    assert classify_url_mode("https://bytedance.larkoffice.com/wiki/Wiki123?table=tbl1") == "bitable"
    assert classify_url_mode("https://bytedance.larkoffice.com/wiki/Wiki123") == "auto"

    parsed = parse_docx_client_vars(
        "Doc1",
        {"block_sequence": ["p1", "t1"]},
        {
            "p1": {"data": {"text": {"initialAttributedTexts": {"text": {"0": "Hello"}}}}},
            "t1": {
                "data": {
                    "rows_id": ["r1"],
                    "columns_id": ["c1", "c2"],
                    "cell_set": {"r1c1": {"block_id": "cell1"}, "r1c2": {"block_id": "cell2"}},
                }
            },
            "cell1": {"data": {"text": {"initialAttributedTexts": {"text": {"0": "Repo"}}}}},
            "cell2": {"data": {"text": {"initialAttributedTexts": {"text": {"0": "InScope"}}}}},
        },
    )
    md_doc = format_markdown(parsed)
    assert "Hello" in md_doc and "Repo | InScope" in md_doc

    md_bitable = format_markdown({
        "ok": True,
        "mode": "bitable",
        "title": "Targets",
        "tables": [{"id": "t1", "name": "Scope", "loaded": 100, "total": 250, "rows": [["Repo", "Tier"], ["a/b", "P1"]]}],
    })
    assert "PARTIAL: loaded 100/250 rows" in md_bitable and "a/b | P1" in md_bitable

    md_sheet = format_markdown({
        "ok": True,
        "mode": "canvas_sheet",
        "title": "Sheet1",
        "sheets": [{"id": "s1", "name": "Main", "rows": [["A", "B"], ["1", "2"]]}],
    })
    assert "## Main (s1)" in md_sheet and "1 | 2" in md_sheet
    print("ok      feishu_reader.py self-test passed (docx, sheet, bitable)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Read Feishu/Lark Docx, Canvas Sheet, or Bitable")
    ap.add_argument("url", nargs="?", help="Feishu/Lark /docx/, /sheets/, /base/, or /wiki/ URL")
    ap.add_argument("--mode", default="auto", choices=["auto", "docx", "sheet", "bitable"], help="Force extraction mode")
    ap.add_argument("--sheet", default=None, help="Target sheet id or name (Canvas sheets)")
    ap.add_argument("--all-sheets", action="store_true", help="Extract every sheet tab in workbook")
    ap.add_argument("--max-rows", type=int, default=500)
    ap.add_argument("--max-cols", type=int, default=30)
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of Markdown summary")
    ap.add_argument("-o", "--output", default=None, help="Optional file path to write output")
    ap.add_argument("--self-test", action="store_true", help="Run offline self-test")
    args = ap.parse_args()

    if args.self_test:
        return run_self_test()
    if not args.url:
        ap.error("url is required unless --self-test is passed")

    detected = classify_url_mode(args.url, args.mode)
    if detected == "docx":
        res = fetch_docx_via_http(args.url)
    else:
        prefer = "bitable" if detected == "bitable" else "sheet"
        res = fetch_cdp_page(
            args.url,
            mode=detected,
            prefer=prefer,
            sheet=args.sheet,
            all_sheets=args.all_sheets,
            max_rows=args.max_rows,
            max_cols=args.max_cols,
        )

    out_text = json.dumps(res, ensure_ascii=False, indent=2) if args.json else format_markdown(res)
    if args.output:
        Path(args.output).expanduser().write_text(out_text + "\n", encoding="utf-8")
    print(out_text)
    return 0 if res.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
