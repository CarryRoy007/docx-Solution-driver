# docx-Solution-driver

opencode 技能包：技术方案 Word 文档编写 + 格式转换。

## 包含技能

### solution-docx — 技术方案智能编写

输入话题，AI 帮你完成全流程：素材分析 → 大纲策划 → 图表设计 → 批注修改 → 内容撰写 → .docx 导出。

**安装**

```bash
# 克隆到 opencode skills 目录
git clone https://github.com/CarryRoy007/docx-Solution-driver.git ~/.config/opencode/skills/docx-Solution-driver

# 或单独链接 solution-docx
ln -s $(pwd)/SKILL.md ~/.config/opencode/skills/solution-docx/SKILL.md
```

**使用**

在 opencode 对话中说：

```
写一个"大模型安全三件套"技术方案
```

AI 会：
1. 检测环境依赖，缺失的提示安装
2. 和用户确认格式（常规/公文/自定义）和输出路径
3. 渐进式设计大纲（一级确认→全量展示→Web 编辑）
4. 生成 SVG 图表 → 渲染 PNG → 字体验证 → Web 批注
5. 用户提交批注 → AI 修改 SVG → 重新渲染
6. 撰写正文 → 导出 .docx

**依赖**

```bash
pip install flask python-docx python-pptx Pillow beautifulsoup4 lxml cairosvg PyMuPDF requests openpyxl
```

### docx-formatter — Word 格式转换

Markdown → .docx，确定性脚本保证格式一致。双模式：普通文档格式 + 公文格式（GB/T 9704-2012）。

**安装**

```bash
pip install python-docx
```

**使用**

```bash
# 普通格式
python3 docx-formatter/scripts/md_to_normal.py input.md output.docx

# 公文格式（红头文件 GB/T 9704-2012）
python3 docx-formatter/scripts/md_to_official.py input.md output.docx

# 验证格式
python3 docx-formatter/scripts/validate_normal.py output.docx
```

**自动编号规则**

| Markdown | 编号 | 字号 |
|----------|------|------|
| `# 标题` | 文档标题 | 16pt |
| `## xxx` | 一、 | 16pt |
| `### xxx` | 1.1 | 14pt |
| `#### xxx` | 1.1.1 | 12pt |
| `###### xxx` | （1） | 12pt |

---

## 一键更新

```bash
bash publish.sh "更新内容说明"
```

## 目录结构

```
├── SKILL.md                     # solution-docx 主工作流
├── requirements.txt             # Python 依赖
├── publish.sh                   # 发布脚本
├── scripts/                     # Python 工具脚本
│   ├── env_checker.py           # 环境依赖检测
│   ├── material_analyzer.py     # 多格式素材解析
│   ├── template_analyzer.py     # 模板 DOCX 分析
│   ├── image_extractor.py       # 图片提取
│   ├── svg_renderer.py          # SVG → PNG（含中文字体检测）
│   ├── drawio_to_png.py         # draw.io → PNG
│   ├── outline_builder.py       # 大纲生成
│   ├── search_helper.py         # 搜索辅助
│   ├── template_writer.py       # 模板写入
│   └── web_preview/             # Web 预览服务
│       ├── server.py            # Flask 服务
│       └── static/              # 前端页面（大纲编辑 + 图表批注）
├── workflows/                   # 子流程文档
├── references/                  # 写作规范 + 图表指南 + 结构模板
├── templates/                   # SVG 图表骨架模板（7个）
│   └── diagram_skeletons/
└── docx-formatter/              # 格式转换工具
    ├── SKILL.md
    └── scripts/
```
