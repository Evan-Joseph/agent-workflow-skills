# 路由与隐私

## 能力边界

AnySearch 提供通用搜索、批量搜索、URL 提取和垂直领域检索。当前公开域包括 `resource`、`social_media`、`finance`、`academic`、`legal`、`health`、`business`、`security`、`ip`、`code`、`energy`、`environment`、`agriculture`、`travel`、`film` 和 `gaming`。

它适合做宽入口、垂直补充和交叉核验。本机已有直接调用一手数据库或专门平台的 Skill 时，专用 Skill 优先，因为其来源、字段和失败模式更清楚。

## 查询分级

| 查询内容 | 是否允许 | 处理方式 |
|---|---:|---|
| 公开法规、公司官网、公开产品信息 | 是 | 可直接搜索，关键结论回到原始来源 |
| 已公开论文题目、DOI、作者 | 是 | 学术专用 Skill 优先，AnySearch 可作补充 |
| 抽象后的技术问题 | 是 | 删除内部项目名、仓库名和私有路径 |
| 未发表论文、审稿意见、私有实验 | 否 | 使用本地文件和学术工作流 |
| 私有代码、客户数据、合同原文 | 否 | 使用本地工具或用户指定的可信系统 |
| 凭据、个人数据、内部 URL | 否 | 不发送，也不做部分遮盖后发送 |

## 隐私事实

AnySearch 官网主页使用“no logging”“zero retention”等表述。其 2026-05-01 生效的隐私政策同时写明：

- 保存 API 调用时间、Key 标识、路由域、状态码、延迟和结果数
- 保存查询内容前 100 个字符作为 `Search Query Summary`
- API 调用日志保留 12 个月
- 完整查询和结果声称不在请求结束后持久保存
- 数据可能在多个司法辖区处理

因此按正式政策而非首页营销文案设定使用边界。

来源：

- https://www.anysearch.com/legal?type=privacy
- https://www.anysearch.com/pricing
- https://github.com/anysearch-ai/anysearch-skill

## 核验规则

- 政策、法律和申报要求：优先政府或主管机构原文。
- 产品和 API 行为：优先官方文档、仓库、Release 和 Issue。
- 新闻和市场信息：至少核对日期、主体和原始发布方。
- 搜索摘要可能截断上下文，不直接据此做高风险判断。
