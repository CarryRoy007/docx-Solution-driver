---
name: solution-docx
description: >
  技术方案、可研报告等 Word 文档编写 Skill。多格式素材解析（PPT/HTML/DOCX/draw.io/PNG/SVG）、
  渐进式大纲设计、图表迭代批注、调研补全、格式委托输出。使用"solution-docx"、"写方案"、"可研报告"、
  "技术方案编写"、"solution generation"、"feasibility study"、"word解决方案"时激活。
compatibility: opencode
metadata:
  source: opencode-autoflow
  owner: yaoyongrui
  phase: implementation
---

# Skill: solution-docx

> 技术方案、可研报告、解决方案文档编写全流程。素材分析 → 大纲策划 → 图表设计 → 内容撰写 → 格式导出。

## 触发条件

用户说"写技术方案"、"可研报告"、"solution-docx"、"生成解决方案文档"、"word方案编写"时激活。

## 核心原则

1. **阶段门控**：每个 Phase 有明确 BLOCKING 检查点，用户确认后才进入下一阶段。绝不跳过任何阶段
2. **渐进式设计**：一级标题确认后，二三各级一次性全量展示，用户反馈后锁定
3. **素材优先**：分析用户提供的全部素材(PPT/HTML/DOCX/draw.io/PNG/SVG)，AI自行判断哪些可能有效，然后以选择题方式让用户确认引用策略
4. **图表结构化**：所有图表使用 SVG 源码生成，渲染 PNG 嵌入文档，保留 SVG 源文件供修改
5. **格式委托**：不重复造轮子，最终 .docx 输出委托给 `docx-formatter` 或用户自有模板
6. **Web 预览强制**：大纲确认和图表预览阶段，必须启动 Web 服务并自动跳转浏览器，用户操作完成后才能继续

---

## Phase -1: 环境检测 (BLOCKING — 每次激活自动执行)

激活 skill 后，立即运行环境检测，不能跳过。

```bash
python3 ${SKILL_DIR}/scripts/env_checker.py --base-dir <project_dir>
```

### 输出解读规则

环境检测输出的是每个依赖项的逐条状态。解读方式：

**看到 `[OK]` → 该项就绪，无需处理。**

**看到 `[WARN]` → 可选依赖缺失，该依赖对应的功能降级。** 必须向用户逐条说明：
- 缺失了什么（名称）
- 会导致什么功能不可用（影响）
- 询问用户是否需要帮助安装

**看到 `[FAIL]` → 关键依赖缺失，skill 无法正常运行。** 必须立即告知用户并停止流程。

示例——正确报告方式：
```
环境检测结果：
  OK  Python 3.13.9
  OK  flask (Web 服务)
  OK  python-docx (Word 生成)
  WARN  drawio CLI 未安装 → draw.io 文件转换不可用
  WARN  LibreOffice 未安装 → PDF 格式巡检不可用

2 项可选依赖缺失。是否需要我帮你安装？(npm/pip install)
```

错误报告方式（禁止）：
"环境就绪（仅 drawio CLI 和 LibreOffice 未安装，不影响本次）" ← 歧义太大

### 自动修复

如果用户同意安装：
```bash
python3 ${SKILL_DIR}/scripts/env_checker.py --bootstrap fix_deps.sh
bash fix_deps.sh
```

---

## Phase 0: 格式 + 模板 + 路径确认 (BLOCKING)

执行前必须完成以下确认。每项确认后才能进行下一项:

### 0.1 格式选择

```
向用户提问:
  "文档需要哪种格式？"
  A. 常规格式 → 使用 docx-formatter 普通模式
  B. 公文格式 → 使用 docx-formatter 公文模式 (GB/T 9704-2012)
  C. 其他 → 收集自定义格式参数(页边距/字体/字号/行距等)
```

### 0.2 模板选择

```
向用户提问:
  "有没有公司自己的方案模板(.docx)? 如有，请提供路径。"
  → 有模板 → 执行 template_analyzer.py:
    python3 ${SKILL_DIR}/scripts/template_analyzer.py <template.docx> --output <project_dir>/00_analysis/template_profile.json
    自动深度分析: 封面布局/各级标题样式(字体/字号/加粗/大纲级别)/正文样式/页边距/页眉页脚
    输出分析报告给用户
  → 无模板 → 使用 docx-formatter 默认规范
```

### 0.3 输出路径

```
向用户提问:
  "输出到哪个目录？"
  确认后自动创建分类子目录结构:
```

输出目录结构(自动创建):
```
<output_root>/<project_name>/
├── 00_analysis/          # 素材分析报告 + 模板分析报告
├── 01_materials/         # 提取的原始素材图片
├── 02_outline/           # 大纲文件
├── 03_diagrams/
│   ├── sources/          # SVG/drawio 源文件
│   └── png/              # 渲染后的 PNG
├── 04_research/          # 调研收集的参考资料
├── 05_drafts/            # 各阶段草稿 Markdown
└── 06_final/             # 最终 .docx
```

---

## Phase 1: 素材收集与分析

### 1.1 素材收集

用户提供素材（文件夹路径/文件路径/URL）。

运行素材解析:
```bash
python3 ${SKILL_DIR}/scripts/material_analyzer.py \
  --inputs <path1> <path2> ... \
  --output <project_dir>/00_analysis/
```

### 1.2 分析内容

脚本自动完成:
- **PPT/PPTX** → 提取每页文本骨架 + 内嵌图片 + 演讲者备注
- **DOCX** → 提取文本结构 + 图片(含图题如"图1、总体架构")
- **HTML** → 提取正文内容 + 引用图片地址
- **draw.io/.drawio** → 标记待转换，记录文件名和路径
- **PNG/SVG/JPG/PDF** → 收集归类，记录元数据(尺寸/来源)
- **URL** → 抓取网页正文

对于图片，提取元信息:
- 图题/说明文字（从 DOCX 邻近段落推断）
- 尺寸
- 来源文件

### 1.3 素材摘要呈现

向用户展示分析摘要:
```
📊 素材分析摘要

发现 N 个素材:
  PPT: 产品介绍.pptx (15页) — 含 8 张图片
  DOCX: 技术白皮书.docx (42页) — 含 12 张图片(有图题)
  draw.io: 网络拓扑.drawio
  图片: 架构图.png, 部署图.png

识别到的图片:
  [X] 图1、总体架构 (来自 技术白皮书.docx)
  [ ] 图2、数据流图 (来自 技术白皮书.docx)
  ...

内容板块:
  - 产品概述 (来自 PPT 第2-5页)
  - 技术架构 (来自 白皮书 第3章)
  - 部署方案 (来自 PPT 第15页)
  ...
```

### 1.4 引用策略确认

对每个素材，以选择题方式确认:

```
素材: 产品介绍.pptx
  引用策略:
  ( ) A. 仅借鉴思想框架，不引用原文
  ( ) B. 摘抄部分描述（自动去品牌化处理）
  ( ) C. 全部忽略，仅作背景参考

素材: 技术白皮书.docx
  引用策略:
  ( ) A. 仅借鉴思想框架
  ( ) B. 摘抄部分章节（指定哪些章节）
  ( ) C. 全部忽略

图片引用:
  ( ) 全部引用  ( ) 仅引用选中的(X张)  ( ) 全部忽略
```

### 1.5 大型素材处理（>50页/大于50张幻灯片）

对于大型素材, 先给出结构摘要, 让用户标记关注区域, 再细化提问:

```
素材: 技术白皮书.docx (142页)
  章节结构:
  1. 前言 (已标记关注)
  2. 术语定义
  3. 理论概述 (已标记关注)
  4. 产品说明
  5. 部署指南 (已标记关注)
  ...

  已标记关注的章节, 其他将在写入时忽略。
```

图片提取:
```bash
python3 ${SKILL_DIR}/scripts/image_extractor.py \
  --input <source_file> \
  --output <project_dir>/01_materials/
```

---

## Phase 2: 渐进式大纲设计 (BLOCKING — 大纲确认前不能进入后续阶段)

### 2.1 确定文档类型

根据用户意图判断文档类型: 技术方案 / 可研报告 / 解决方案 / 立项报告 / 其他

### 2.2 一级标题设计

结合素材分析结果、文档类型模板、用户策略，生成一级标题建议，附设计思路和素材支撑标注。

用户确认一级标题后，一次性生成完整大纲(含二三级)。

### 2.3 全量大纲展示

生成完整大纲后，以结构化格式展示，并明确告知用户两种修改方式：

```
请审阅。你可以:
  1. 聊天直接说哪里要改
  2. 说"打开页面"，我打开 Web 大纲编辑页拖拽修改
```

### 2.4 大纲编辑 (BLOCKING 检查点)

用户说"打开页面"/"网页编辑"/"线上编辑" → 立即启动 Web 服务：

```bash
python3 ${SKILL_DIR}/scripts/web_preview/server.py \
  --project <project_dir> \
  --port 5100
```

**不要加 `--no-browser` 参数**，浏览器会自动打开到大纲编辑页。

**服务器启动后必须等用户完成操作。判断完成的方式：**
- 服务器进程退出（用户点击了"保存并继续"或"退出"按钮）
- 用户聊天告知"好了"/"确认完毕"

**服务器崩溃处理：**
如果用户反馈页面访问不了或服务器报错：
- 检查端口是否被占用，换一个端口重试（5101, 5102...）
- 告知用户当前状态，不能假装一切正常
- 重试后仍失败 → 回退到纯聊天模式确认大纲

### 2.5 大纲锁定

用户确认后:
- 大纲写入 `<project_dir>/02_outline/outline.json`
- 保存 checkpoint: `{phase: "phase2", outline_locked: true}`
- **锁定的同时通知用户："大纲已锁定。接下来进入调研环节。"**

---

## Phase 3: 调研补全 (BLOCKING — 仅在用户素材不足时执行)

### 3.1 识别内容缺口

对比大纲与已有素材, 识别缺乏内容支撑的章节:

```
识别到以下章节缺乏素材支撑:
  - 1.1 政策背景与行业趋势 → 需要外部调研
  - 四、效益分析 → 需要行业参考数据

是否针对以上章节开启搜索调研?
```

用户确认后执行搜索。如果用户说"跳过调研"/"直接写"，则跳过 Phase 3 进入 Phase 4。

对每个缺口, 进行结构化搜索:

```bash
python3 ${SKILL_DIR}/scripts/search_helper.py \
  --queries "行业政策分析" "技术方案效益评估" "信息化项目风险评估" \
  --output <project_dir>/04_research/
```

搜索策略:
- 关键词重组: 技术术语 + 方案关键词
- 过滤低质量内容: 排除纯营销文案、噱头标题、信息密度低的页面
- 优先引用: 政府文件、行业白皮书、标准规范、权威媒体深度报道
- 每条结果输出: 标题、URL、摘要、可信度评分

### 3.3 调研结果呈现

向用户展示并确认采纳:

```
🔍 搜索结果 (共 N 条, 精选 5 条):

1. 《XX行业十四五规划》— 政府官网 — 可信度: 高
   "明确提出到2025年XX领域要实现..."
   → 建议用于 1.1 政策背景

2. 《XX技术白皮书》— 中国信通院 — 可信度: 高
   ...

采纳哪些?
```

---

## Phase 4: 图表迭代设计 (BLOCKING — 图表确认前不能进入内容撰写)

### 4.0 风格选择 (BLOCKING — 必须在生成图表前确认)

在识别图表位置之后、生成 SVG 之前，必须先让用户选择图表风格。**同一份文档的所有图表必须使用统一风格**。

向用户展示风格选项（以文字+色块方式在聊天中呈现）：

```
请选择图表风格：

🟦 1. Claude 风格 (推荐) — 深色标题栏渐变 + 白色内容卡片 + 浅阴影
     主色: #2563EB(蓝) #059669(绿) #d97706(橙) #6366f1(紫)
     → 参考 deploy_gateway 的设计语言

🟩 2. 商务蓝 — 全蓝系渐变 + 白色模块 + 方正布局
     主色: #1e40af #2563eb #3b82f6 #60a5fa #93bbfd
     → 适合政府/国企正式方案

🟪 3. 科技灰 — 深灰背景 + 彩色高亮 + 科技感
     主色: #1e293b #334155 #3b82f6 #10b981 #f59e0b
     → 适合互联网/科技公司方案

🟧 4. 暖色商务 — 暖色调 + 卡片式布局
     主色: #d97706 #f59e0b #fbbf24 #92400e #b45309
     → 适合咨询/服务类方案
```

用户选择后，所有后续生成的 SVG 统一使用该风格的颜色、阴影、圆角、标题样式。

如果用户说"随便"/"默认"，使用 Claude 风格。

### 4.1 识别需要绘图的位置

扫描锁定的大纲, 识别需要图表的章节位置，向用户确认图表清单。

### 4.2 图表生成与渲染

对每个确认的图表，依次：
1. 生成 SVG 源码 → 保存到 `03_diagrams/sources/`
   - **所有 `<text>` 元素必须使用中文字体栈**: `font-family="PingFang SC, Heiti SC, Microsoft YaHei, Hiragino Sans GB, Arial Unicode MS, sans-serif"`
   - **不得**仅使用 `font-family="sans-serif"`（会导致 cairosvg 渲染中文变方框）
2. 渲染为 PNG → 保存到 `03_diagrams/png/`

### 4.2b 中文字体验证 (BLOCKING — 渲染后必须执行)

渲染完第一张图表后，立即验证中文字体是否正确渲染：

```bash
python3 ${SKILL_DIR}/scripts/svg_renderer.py \
  --input <project_dir>/03_diagrams/sources/<first_diagram>.svg \
  --output /dev/null \
  --verify-chinese
```

解读输出：
- `status: "ok"` → 中文字体正常，继续渲染其余图表
- `status: "tofu_risk"` → 中文字体不可用，**必须立即告知用户**：

```
当前环境中文字体渲染失败 (complexity=0.xx，低于阈值0.2)。
生成的 PNG 图表中中文将显示为方框。

可选方案：
  A. 安装中文字体后重试 (推荐)
  B. 改用英文标签重新生成图表
  C. 暂不处理，先继续 (图表文字会有问题)

你选择哪个？
```

如果用户选择方案 B（英文回退），重新生成所有 SVG 时使用英文标签：
- 将中文标签替换为英文（如"接入层"→"Access Layer"，"用户输入"→"User Input"）
- 同时保留 SVG 源文件，方便用户后续自行翻译为中文

**所有 SVG 最终都应使用正确的字体栈，无论当前环境是否支持。**

### 4.3 启动 Web 预览 (BLOCKING 检查点 — 必须执行)

所有图表生成后，启动 Web 预览服务。**不要加 `--no-browser`**，浏览器会自动打开到图表批注页：

```bash
python3 ${SKILL_DIR}/scripts/web_preview/server.py \
  --project <project_dir> \
  --port 5100
```

**启动成功后，必须在聊天中向用户输出以下提示**（强制）:

```
浏览器已打开图表批注页面。操作步骤:

1️⃣ 查看图表：点击左侧列表切换图表，可用 ＋/− 按钮或 Ctrl+滚轮 缩放查看细节
2️⃣ 提交批注：点击图表中的元素（蓝色边框选中），在右侧面板输入批注内容，点击"提交批注"
3️⃣ 全部批注提交完毕后，点击底部 "确认图表" 按钮
4️⃣ AI 将读取你的批注，逐条反馈并修改 SVG，随后进入内容撰写

现在去看图表吧 👆
```

**一定要告知用户先提交批注，再由 AI 处理，不要直接跳到内容撰写。**

### 4.4 服务器启动验证 (必须执行)

启动服务后，必须验证服务是否正常运行：

```bash
# 等待 1 秒后验证
sleep 1
curl -s -o /dev/null -w "%{http_code}" http://localhost:5100/
```

如果返回 `200` → 服务正常，告知用户浏览器已打开。
如果返回非 200 或连接失败 → **服务启动失败，必须告知用户**：
- 告知用户当前状态："Web 预览服务启动失败"
- 尝试换端口重试（5101, 5102...）
- 两次重试后仍失败 → 回退到聊天模式，告知用户无法预览但可以继续

**严禁在服务器不可用时假装一切正常，然后跳过图表环节直接进入 Phase 5。**

### 4.5 图表批注交互

用户在图表批注页:
1. 查看渲染后的图表
2. 鼠标框选 SVG 元素(高亮区域)
3. 输入批注文本 → 提交
4. AI 读取批注 → 修改 SVG 源码 → 重新渲染 PNG → 用户刷新预览
5. 用户确认 → 保存最终版本

批注数据保存到 `<project_dir>/03_diagrams/annotations.json`

### 4.5b AI 批注反馈 (BLOCKING — 收到批注后必须先处理)

当服务器 shutdown（用户点击了"确认图表"或"关闭预览..."）后，AI 必须执行以下步骤。**严禁跳过批注直接进入 Phase 5。**

**Step 1: 读取批注和确认状态**
```bash
# 检查 checkpoint 是否已确认
cat <project_dir>/.checkpoint.json
# 读取所有批注
cat <project_dir>/03_diagrams/annotations.json
```

**Step 2: 判断是否需要处理批注**
- 如果 `diagrams_confirmed` 为 true 但 `annotations.json` 中仍有未处理的批注 → **必须先处理批注**
- 如果完全没有批注 → 可以直接进入 Phase 5

**Step 3: 逐条处理批注** — 对每一条批注：
1. 根据 `element_id` 定位 SVG 中的具体元素
2. 根据批注文本理解用户意图，修改 SVG 源码
3. 保存修改后的 SVG

**Step 4: 重新渲染 PNG**
```bash
python3 ${SKILL_DIR}/scripts/svg_renderer.py --input <svg_path> --output <png_path> --scale 2
```

**Step 5: 向用户反馈**（必须逐条列出）:
```
已处理你在 Web 页面提交的批注：

  arch_3piece.svg:
    ✅ mavas-zone "与下方框图重叠" → 将 MAVAS 区域下移 40px，拉开间距
    ✅ llm-service "挡住了" → 调整 LLM 服务块位置，不再重叠

  deploy_3piece.svg:
    ✅ zone-external "三个框分布不均匀" → 重新均分三个模块的 x 坐标

所有修改已完成，PNG 已重新渲染。现在进入内容撰写。
```

如果批注涉及复杂布局调整，AI 应尽力修改；确实无法通过修改 SVG 属性解决的（如"配色不好看"），告知用户："配色方面建议在 SVG-Edit 中打开 SVG 源文件调整配色，我给几个方案参考。"

用户确认后 → 进入 Phase 5 内容撰写。

### 4.6 图表确认 (BLOCKING 检查点)

全部图表确认后:
- 保存最终 SVG 源文件和对应的 PNG
- 保存 checkpoint: `{phase: "phase4", diagrams_confirmed: N}`
- **明确告知用户："图表已确认。接下来进入内容撰写。"**
- 用户确认后才开始 Phase 5

---

## Phase 5: 内容撰写 (BLOCKING — 仅在大纲锁定、图表确认后开始)

### 5.1 前置条件检查

撰写前必须确认：
- [ ] 大纲已锁定 (`02_outline/outline.json` 存在)
- [ ] 图表已确认 (所有需要图的位置都有对应的 PNG)
- [ ] 调研已完成 (如有调研需求)

如果任何前置条件不满足，不能进入 Phase 5。

### 5.2 写前准备

加载以下上下文:
- 锁定的大纲 (`02_outline/outline.json`)
- 素材分析报告 (`00_analysis/`)
- 引用策略决策
- 调研结果 (`04_research/`)
- 确认的图表清单
- 写作规范 (`references/writing-standards.md`)

### 5.3 逐节撰写

按大纲顺序, 逐节撰写 Markdown 正文:

- 遵循 `references/writing-standards.md` 的写作规范
- 图表引用格式: `![图题](03_diagrams/png/xxx.png)` (docx-formatter 会自动编号和格式化)
- 对引用素材中的内容: 执行去品牌化(剔除产品名/型号/公司名, 替换为通用描述)
- 草稿保存到 `<project_dir>/05_drafts/`

### 5.4 Markdown 标题层级对齐

docx-formatter 的自动编号规则:
| Markdown | 自动编号 | 字号 | 加粗 | 大纲级别 |
|----------|---------|------|------|---------|
| `# 标题` | 文档标题 | 16pt | 是 | — |
| `## xxx` | 一、 | 16pt | 是 | L0 |
| `### xxx` | 1.1 | 14pt | 是 | L1 |
| `#### xxx` | 1.1.1 | 12pt | 是 | L2 |
| `##### xxx` | 1.1.1.1 | 12pt | 是 | L3 |
| `###### xxx` | （1） | 12pt | 是 | L4 |

**不要手动添加标题序号**（脚本自动编号）。也不要在标题文本中包含"一、"、"1.1"等序号前缀。

如果大纲有 3 级标题结构（一、→ 1.1 → 1.1.1），对应的 Markdown：
- 一级 (`##`) → 大纲第一层 → 生成"一、二、三..."
- 二级 (`###`) → 大纲第二层 → 生成"1.1, 1.2, 2.1..."
- 三级 (`####`) → 大纲第三层 → 生成"1.1.1, 1.1.2, 2.1.1..."

如果有四级，第四级用 `######` → 生成"(1), (2)..."

**总结：三级编号用 1.1.1 格式，不用 (1)。四级才用 (1)。**

加载以下上下文:
- 锁定的大纲 (`02_outline/outline.json`)
- 素材分析报告 (`00_analysis/`)
- 引用策略决策
- 调研结果 (`04_research/`)
- 确认的图表清单
- 写作规范 (`references/writing-standards.md`)

### 5.2 逐节撰写

按大纲顺序, 逐节撰写 Markdown 正文:

- 遵循 `references/writing-standards.md` 的写作规范
- 图表引用格式: `![图题](03_diagrams/png/xxx.png)` (docx-formatter 会自动编号和格式化)
- 对引用素材中的内容: 执行去品牌化(剔除产品名/型号/公司名, 替换为通用描述)
- 借鉴思想的部分: 用自己的语言重新组织, 保持信息密度
- 草稿保存到 `<project_dir>/05_drafts/`

### 5.3 去品牌化处理

自动识别并处理:
- 产品名称 → 替换为 "本方案" / "该平台"
- 型号/版本号 → 替换为通用描述
- 公司名称 → 替换为 "我方" / "建设方"
- Logo 图片 → 标记提醒用户替换

---

## Phase 6: 格式委托与导出

### 6.1 格式转换

#### 有用户模板:

1. 读取模板分析结果 (`00_analysis/template_profile.json`)
2. 打开模板 .docx, 使用模板样式逐节写入内容
3. 模板缺失的样式(如用户模板只有到二级标题), 参考 docx-formatter 规范补充
4. 保留模板的封面、页眉页脚、背景

```bash
python3 ${SKILL_DIR}/scripts/template_writer.py \
  --template <user_template>.docx \
  --markdown <project_dir>/05_drafts/final.md \
  --profile <project_dir>/00_analysis/template_profile.json \
  --output <project_dir>/06_final/output.docx
```

#### 无用户模板:

委托给 docx-formatter:

```bash
# 常规格式
python3 ~/.config/opencode/skills/docx-formatter/scripts/md_to_normal.py \
  <project_dir>/05_drafts/final.md \
  <project_dir>/06_final/output.docx

# 公文格式
python3 ~/.config/opencode/skills/docx-formatter/scripts/md_to_official.py \
  <project_dir>/05_drafts/final.md \
  <project_dir>/06_final/output.docx
```

### 6.2 验证

```bash
# 常规格式验证
python3 ~/.config/opencode/skills/docx-formatter/scripts/validate_normal.py \
  <project_dir>/06_final/output.docx

# 公文格式验证
python3 ~/.config/opencode/skills/docx-formatter/scripts/validate_official.py \
  <project_dir>/06_final/output.docx
```

### 6.3 交付检查清单

完成后报告:
- 文档类型和格式模式
- 输出 `.docx` 路径
- 验证结果
- 图表清单 (SVG 源文件 + PNG 文件)
- 使用的素材及其引用策略
- 去品牌化处理的章节
- 缺失的图片/图表(如用户未提供)
- 字体安装提示(如相关)

---

## 非多模态模型回退策略

当模型无法直接查看图片内容时:

1. **素材图片**: 解析图题/邻近文字描述, 呈现元数据给用户确认
2. **素材图片无图题**: 报告尺寸/来源/文件名, 建议用户手动查看后告知是否引用
3. **图表生成**: SVG 是纯文本格式, 模型可直接读写; 渲染 PNG 仅用于用户预览, 不需要模型看
4. **用户反馈**: 引导用户在 Web 批注界面中标注具体修改意见, 模型根据 SVG 元素 ID 和批注文本执行修改

---

## 图片格式统一策略

所有插入文档的图片统一为 PNG:
- 原始素材图片(PPT/DOCX提取): 自动提取为 PNG
- draw.io 文件: 转换为 PNG
- SVG 图表: 渲染为 PNG
- HTML 图表: 渲染为 PNG
- 原始PNG/JPG: 保持原样或转换为 PNG

所有源文件保留在 `03_diagrams/sources/` 或 `01_materials/` 中, 供用户后续修改。

---

## 鲁棒性、自恢复与自适应

### 环境检测

skill 激活时自动运行环境检测:

```bash
python3 ${SKILL_DIR}/scripts/env_checker.py --base-dir <project_dir> --json
```

检测项目:
- Python 版本 (>=3.9)
- 关键依赖: flask, python-docx, python-pptx, Pillow, lxml (缺失则功能退化)
- 可选依赖: cairosvg, PyMuPDF, beautifulsoup4, requests, openpyxl (缺失则对应功能不可用)
- 系统工具: drawio CLI, LibreOffice (缺失则使用 fallback)

### 分级退化策略

| 缺失依赖 | 影响 | 回退方案 |
|---------|------|---------|
| flask | Web 预览不可用 | 所有交互通过聊天完成 |
| python-docx | 无法生成 .docx | 仅输出 Markdown 草稿 |
| python-pptx | 无法解析 PPT | 跳过 PPT 素材, 告知用户 |
| cairosvg | SVG → PNG 不可用 | 图表仅保存 SVG, 提示用户手动转换 |
| PyMuPDF | 无法解析 PDF | 提示用户提供文本版 PDF 或手动输入 |
| drawio CLI | draw.io 转换失败 | 使用内置 XML 解析器提取内容 |
| LibreOffice | PDF 格式巡检不可用 | 跳过格式验证步骤 |

### 自动修复

env_checker 可生成一键修复脚本:

```bash
python3 ${SKILL_DIR}/scripts/env_checker.py --bootstrap fix_deps.sh
bash fix_deps.sh
```

### 断点续传

每个 Phase 结束时自动保存 checkpoint 到 `<project_dir>/.checkpoint.json`:

| Phase | Checkpoint 标记 |
|-------|----------------|
| Phase 0 | `{phase: "phase0", format: "normal\|official\|custom", template: "..."}` |
| Phase 1 | `{phase: "phase1", materials_count: N, strategy: {...}}` |
| Phase 2 | `{phase: "phase2", outline_locked: true}` |
| Phase 4 | `{phase: "phase4", diagrams_confirmed: N}` |
| Phase 5 | `{phase: "phase5", draft_complete: true}` |
| Phase 6 | `{phase: "phase6", output_path: "..."}` |

如果流程中断 (模型超时/网络断开/用户关闭会话), 重新激活 skill 时:
1. 运行 `api/status` 检查项目目录中各阶段产物
2. 读取 `.checkpoint.json` 确定中断位置
3. 询问用户: "检测到上次中断于 Phase X, 是否从该位置恢复?"
4. 恢复: 加载已锁定的数据 (大纲/图表/草稿), 继续后续流程

### 容错原则

- 脚本执行前先检查依赖, 不可用的功能主动告知用户替代方案
- 文件不存在/格式错误时不崩溃, 记录错误并继续处理其他文件
- Markdown 草稿每个章节完成后自动写入 `05_drafts/`, 避免全量丢失

### 服务器启动与崩溃恢复

启动 Web 服务后，必须执行健康检查：

```bash
# 等待 1 秒后验证
sleep 1
curl -s http://localhost:<port>/api/health
```

- 返回 `{"status":"ok"}` → 正常，告知用户浏览器已自动打开
- 连接拒绝或超时 → 失败，尝试以下恢复步骤：
  1. 换端口重试（`--port 5101`）
  2. 再次健康检查
  3. 两次重试后仍失败 → 回退到聊天模式，明确告知用户

**禁止在服务器不可用时跳过图表环节、假装一切正常。**

---

## Web 预览页关系

两个独立页面，AI 按流程阶段自动启动：

| 阶段 | 自动打开页面 | 用户操作 |
|------|------------|---------|
| Phase 2 大纲确认 | `/outline` | 拖拽排序/重命名 → 点击"保存大纲" |
| Phase 4 图表预览 | `/diagrams` | 查看图表/框选批注 → 点击"确认图表" |

**BLOCKING 规则：**
- 用户未在网页上点击"保存并继续"或"退出"前，不能进入下一阶段
- 如果用户说"好了"/"确认了"但服务还在运行 → 询问用户是否已在页面操作完毕
- 如果用户反馈页面打不开 → 立即诊断并告知状态，不能假装无事发生

用户路径:
- 大纲确认时 → AI 启动服务，浏览器自动打开 `/outline`
- 图表预览时 → AI 启动服务，浏览器自动打开 `/diagrams`
- 页面顶栏有大纲编辑和图表批注两个链接，导航清晰

### 启动服务的正确命令

**绝不要使用 `--no-browser` 参数**（除非是自动化测试）：

```bash
# 正确 — 浏览器自动打开
python3 ${SKILL_DIR}/scripts/web_preview/server.py --project <project_dir>

# 正确 — 指定端口
python3 ${SKILL_DIR}/scripts/web_preview/server.py --project <project_dir> --port 5100

# 错误 — 用户不知道去哪看
python3 ${SKILL_DIR}/scripts/web_preview/server.py --project <project_dir> --no-browser &
```

**不要使用 `&` 后台运行** — 这会导致 shell 工具超时，且无法检测服务器崩溃。改用 `--live` 模式让服务器自行管理空闲超时。

---

## 脚本说明

| 脚本 | 用途 |
|------|------|
| `env_checker.py` | 环境依赖检测、分级退化、自动修复脚本生成 |
| `material_analyzer.py` | 多格式素材解析 (PPT/DOCX/HTML/draw.io/PDF/图片/URL) |
| `template_analyzer.py` | 用户模板 .docx 全自动深度分析 |
| `image_extractor.py` | 从 PPT/DOCX/HTML 提取内嵌图片为 PNG |
| `drawio_to_png.py` | draw.io 文件 → PNG (CLI + XML 双模式回退) |
| `svg_renderer.py` | SVG 源码 → PNG 批量渲染 |
| `search_helper.py` | 结构化搜索与质量过滤 |
| `outline_builder.py` | 大纲生成/编辑/序列化工具 |
| `template_writer.py` | 基于用户模板的 Markdown→DOCX 写入 |
| `web_preview/server.py` | Web 预览服务 (大纲编辑 `/outline` + 图表批注 `/diagrams` + 断点续传 API) |
