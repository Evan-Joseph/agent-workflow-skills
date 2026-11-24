# 网页阅读

通用网页、RSS。

## 通用网页 (Jina Reader)

```bash
# 读取任意网页内容
curl -s "https://r.jina.ai/URL"

# 示例
curl -s "https://r.jina.ai/https://example.com/article"
```

**适用场景**: 大多数网页可以直接用 Jina Reader 读取。

## Web Reader (MCP)

```bash
# 读取网页内容 (Markdown 格式)
mcporter call 'web-reader.webReader(url: "https://example.com")'

# 保留图片
mcporter call 'web-reader.webReader(url: "https://example.com", retain_images: true)'

# 纯文本格式
mcporter call 'web-reader.webReader(url: "https://example.com", return_format: "text")'
```

**适用场景**: 需要更精确控制输出格式时使用。

## RSS (feedparser)

```python
python3 -c "
import feedparser
for e in feedparser.parse('FEED_URL').entries[:5]:
    print(f'{e.title} — {e.link}')
"
```

**适用场景**: 订阅博客、新闻源、播客等 RSS feed。

## 飞书 / Lark 在线文档、Canvas 表格与多维表格

飞书 `/sheets/`、`/base/`、`/wiki/` 中的 Canvas 表格与 Bitable 记录不会出现在普通 HTML `innerText` 中（`r.jina.ai` 或 `cdp-ctl text` 会返回空表格）。遇到此类链接直接调用通用三合一提取器（`docx` 走 `client_vars` `mode=1+4`，`sheets`/`bitable` 经 `:9223` 读取 `window.spreadApp` / `window.bitableStore` 并自动收尾清理标签）：

```bash
python3 $HOME/.agents/skills/document-parsing/scripts/feishu_reader.py "https://example.larkoffice.com/wiki/TOKEN?sheet=SHEET_ID" --all-sheets
```

## 选择指南

| 场景 | 推荐工具 |
|-----|---------|
| 通用网页 | Jina Reader (`curl r.jina.ai`) |
| 需要图片/格式控制 | web-reader MCP |
| 飞书/Lark Docx、Canvas 表格、多维表格 | [`feishu_reader.py`](../../document-parsing/scripts/feishu_reader.py) |
| RSS 订阅 | feedparser |
