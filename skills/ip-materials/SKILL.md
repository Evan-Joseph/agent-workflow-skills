---
name: ip-materials
description: "知识产权申报材料生成与交底书编写中枢。支持中国软件著作权（软著申请表、60页前后端源码提取、用户操作手册规范排版）以及中国发明/实用新型专利技术交底书（专利点挖掘、权利要求书草案、技术方案与论文转专利 Paper2Patent）全流程生成。"
metadata:
  short-description: 知识产权材料生成：软著60页代码与专利技术交底书
---

# Intellectual Property Materials (软著与专利交底)

统一中国软件著作权与专利技术交底书的生成规范。

## 运行时契约与环境约束 (Runtime Contract)

- **统一解释器**：必须固定使用 `python3`（对应 `~/.agents/config/python-runtimes.json` 中的 `miniconda-agent-general` 运行时，包含 `python-docx`、`lxml` 等）。
- **执行命令范例**：
  ```bash
  python3 $HOME/.agents/skills/ip-materials/scripts/check_environment.py --out-dir 软件著作权申请资料/草稿
  ```
- **Agent 防呆红线**：
  - 严禁调用时自作主张创建临时虚拟环境（如 `python -m venv .venv` 或 `conda create`）；
  - 严禁在 Skill 目录或解释器中随意执行 `pip install`；
  - 遇到依赖或环境异常，停止执行并统一按 `python-runtimes.json` 规范维护单一真相源，或向用户汇报。
- **排版与生成环境**：支持原生 OpenXML 校验与 `docx-openxml` 模式，输出文档完全兼容本机 ONLYOFFICE。

## 一、 软件著作权申请资料生成

生成符合中国版权保护中心（CPCC）审验标准的整套申请文档。

### 核心铁律
- **代码来自真实源码**：严禁 AI 编造假代码。优先按业务逻辑抽取前端/核心后端源码（入口、路由、业务组件、接口定义）。
- **严格 60 页格式**：前 30 页 + 后 30 页，每页不低于 50 行（总计约 3000 行有效代码），包含标准页眉页脚、软件全称与版本号。
- **操作手册业务化**：必须按真实软件操作界面展开，图文并茂，具有目录、功能介绍、系统环境与详细操作步骤。
- **输出目录规范**：固定保存在当前项目工作区下的 `软件著作权申请资料/`。
- **个人成果与委托代办严格隔离**：撰写与归档前先核对 `$HOME/.agents/skills/local-machine-profile/references/user-facts-and-portfolio.md`，明确区分“第一著作权人自有项目”与“外部委托或协作项目”；尚处审查/补正期的软著及代办材料严禁混入个人对外履历。

### 真实流水线命令与门禁
```bash
SKILL_DIR=$HOME/.agents/skills/ip-materials
PY=python3

# 1. 环境检查与项目结构扫描
$PY $SKILL_DIR/scripts/check_environment.py --out-dir 软件著作权申请资料/草稿
$PY $SKILL_DIR/scripts/analyze_project.py --project . --out 软件著作权申请资料/草稿/项目分析.json

# 2. 生成业务理解草稿与候选代码筛选（生成后须由用户确认并执行 confirm_stage.py）
$PY $SKILL_DIR/scripts/generate_business_context.py --project . --analysis 软件著作权申请资料/草稿/项目分析.json --software-name "<软件全称>" --out-dir 软件著作权申请资料/草稿
$PY $SKILL_DIR/scripts/propose_code_selection.py --project . --analysis 软件著作权申请资料/草稿/项目分析.json --out-dir 软件著作权申请资料/草稿
$PY $SKILL_DIR/scripts/confirm_stage.py --out-dir 软件著作权申请资料/草稿 --stage business --note "<确认记录>"
$PY $SKILL_DIR/scripts/confirm_stage.py --out-dir 软件著作权申请资料/草稿 --stage code-selection --note "<确认记录>"

# 3. 抽取前 30 页 + 后 30 页源码草稿（自动按 84 显示列折行并清理陈旧草稿）与生成申请表
$PY $SKILL_DIR/scripts/extract_code_material.py --project . --software-name "<软件全称>" --selection 软件著作权申请资料/草稿/代码文件选择.json --out-dir 软件著作权申请资料/草稿
$PY $SKILL_DIR/scripts/generate_application_info.py --analysis 软件著作权申请资料/草稿/项目分析.json --code-manifest 软件著作权申请资料/草稿/代码提取清单.json --software-name "<软件全称>" --business-context 软件著作权申请资料/草稿/业务理解.json --out-dir 软件著作权申请资料/草稿
$PY $SKILL_DIR/scripts/confirm_stage.py --out-dir 软件著作权申请资料/草稿 --stage application --note "<确认记录>"

# 4. 生成操作手册草稿、整理截图与最终构建正式 Word/TXT
$PY $SKILL_DIR/scripts/capture_screenshots.py --manual-dir 软件著作权申请资料/用户截图 --out-dir 软件著作权申请资料/截图
$PY $SKILL_DIR/scripts/generate_manual_draft.py --analysis 软件著作权申请资料/草稿/项目分析.json --software-name "<软件全称>" --business-context 软件著作权申请资料/草稿/业务理解.json --out-dir 软件著作权申请资料/草稿
$PY $SKILL_DIR/scripts/confirm_stage.py --out-dir 软件著作权申请资料/草稿 --stage manual --note "<确认记录>"
$PY $SKILL_DIR/scripts/build_docx_from_md.py --draft-dir 软件著作权申请资料/草稿 --out-dir 软件著作权申请资料 --software-name "<软件全称>" --version "<版本号>"
```

### 按需参考规范
- 申请表字段规范：[`references/application_fields.md`](./references/application_fields.md)
- 业务理解提炼规则：[`references/business_understanding_rules.md`](./references/business_understanding_rules.md)
- 源码文件筛选与 60 页规则：[`references/code_selection_rules.md`](./references/code_selection_rules.md)、[`references/copyright_material_rules.md`](./references/copyright_material_rules.md)
- 操作手册结构与排版：[`references/manual_structure.md`](./references/manual_structure.md)

## 二、 中国专利技术交底书编写 (Patent Disclosure & Paper2Patent)

支持从科研论文（PDF/LaTeX）、原型设计或项目代码中提炼专利创新点，编写符合 CNIPA 审查标准的交底书。完整拆解方法、附图标记规范与交付前 8 项门禁自检详见 [`references/patent-disclosure-guide.md`](./references/patent-disclosure-guide.md)。

### 撰写规范与逻辑
1. **背景技术与现有技术缺陷**：明确现有方案的不足，杜绝贬低性词汇，用技术指标说话。
2. **发明目的**：针对缺陷提出解决目标。
3. **技术方案与权利要求草案**：
   - 独立权利要求：记载解决技术问题的全部必要技术特征；
   - 从属权利要求：进一步限定的细节特征；
   - 遵循“先权利要求、后具体实施方式”的专业逻辑。
4. **有益效果**：量化技术方案带来的性能提升、抗干扰能力、计算开销降低或精度提升。
5. **附图说明与具体实施方式**：提供逻辑架构图、时序图、流程图及至少一个具体实施例。

### 论文转专利 (Paper to Patent)
- 提取论文中的 Methodology 与 Architecture 作为核心方案；
- 将实验消融分析（Ablation Study）转化为从属权利要求保护点；
- 保持技术公开充分，避免过度泛化导致审查驳回。
