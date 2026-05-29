# 图表迭代设计子流程

> Phase 4 执行时的详细操作指南。

## 0. 风格选择 (BLOCKING — 必须在生成图表前执行)

在识别图表位置之前，必须先让用户选择图表风格。同一份文档的所有图表使用统一风格。

### 风格选项

以文字+色块方式在聊天中呈现：

```
🟦 1. Claude 风格 (推荐) — 深色标题渐变+白色卡片+浅阴影
     主色: #2563EB(蓝) #059669(绿) #D97706(橙) #6366F1(紫)

🟩 2. 商务蓝 — 全蓝系梯度+方正布局
     主色: #1E40AF #2563EB #3B82F6 #60A5FA #93BBFD

🟪 3. 科技灰 — 深灰背景+彩色高亮
     主色: #1E293B #334155 #3B82F6 #10B981 #F59E0B

🟧 4. 暖色商务 — 暖色系+卡片式
     主色: #D97706 #F59E0B #FBBF24 #92400E #B45309
```

### 风格应用规则

选定风格后，所有 SVG 必须遵循：
- 统一的颜色调色板（主色用于标题栏/渐变，辅色用于模块区分）
- 统一的圆角半径（标题栏 rx=10，模块卡片 rx=6）
- 统一的阴影效果（feDropShadow, flood-opacity=0.12）
- 统一的标题样式（font-size=16 bold, 白色文字在渐变背景上）
- 统一的边框线宽（1.5px）

## 1. 识别需要绘图的位置

扫描锁定的大纲, 识别需要图表的章节:

### 识别规则
- 章节标题含"架构/流程/拓扑/部署/结构/模型/示意" → 必出图
- 章节含"对比/比较/选型" → 建议出对比表
- 章节含"计划/里程碑/步骤" → 建议出甘特图/路线图
- 技术方案类文档每个一级标题至少1张图

### 输出格式

```
建议在以下位置插入图表:

📊 2.1 总体架构 → 系统架构图 (分层架构)
📊 2.2 数据流转 → 数据流图
📊 3. 实施步骤 → 里程碑甘特图
📊 4.1 效益对比 → 对比柱状图

确认? 要增减吗?
```

## 2. 图表类型选择

| 需求 | 建议图表类型 |
|------|------------|
| 展示系统组成和关系 | 分层架构图 |
| 展示数据/业务流程 | 流程图 (带箭头) |
| 展示网络设备连接 | 网络拓扑图 |
| 展示时间安排 | 甘特图/时间轴 |
| 展示对比关系 | 柱状图/雷达图 |
| 展示比例构成 | 饼图/环形图 |
| 展示组织关系 | 组织架构图 |
| 展示逻辑关系 | 思维导图 |

## 3. SVG 生成

使用 SVG 生成图表, 遵循以下规范:
- viewBox 统一使用 `0 0 960 640` (16:10, 适合文档嵌入)
- 所有可交互元素必须有 `id` 属性 (供批注定位)
- 使用 `<g id="...">` 分组
- 不使用 `<foreignObject>`, `<style>`, 动画
- 中文内容直接写在 `<text>` 中

**字体必须指定中文字体栈**（否则渲染 PNG 时中文变成方框 □ ）:
```xml
font-family="PingFang SC, Heiti SC, Microsoft YaHei, Hiragino Sans GB, Arial Unicode MS, sans-serif"
```
这确保 cairosvg 在 macOS/Windows/Linux 上都能正确渲染中文字符。

- 颜色使用企业常用的蓝色系/灰色系

### 参考模板

`templates/diagram_skeletons/` 中的 SVG 骨架模板可作为起点修改。

## 4. 渲染与预览

```bash
# 渲染为 PNG
python3 ${SKILL_DIR}/scripts/svg_renderer.py \
  --input <project_dir>/03_diagrams/sources/xxx.svg \
  --output <project_dir>/03_diagrams/png/xxx.png

# 启动图表批注预览
python3 ${SKILL_DIR}/scripts/web_preview/server.py \
  --project <project_dir> \
  --port 5100
```

## 5. 批注迭代

用户的批注会保存在 `<project_dir>/03_diagrams/annotations.json`。

每次收到批注后:
1. 读取 annotations.json
2. 根据 element_id 定位 SVG 中的元素
3. 执行修改 (移动/换颜色/改文字/增删元素)
4. 重新渲染 PNG
5. 通知用户刷新预览

## 6. 最终确认

所有图表确认后:
1. 最终 SVG 保存在 `03_diagrams/sources/`
2. 最终 PNG 保存在 `03_diagrams/png/`
3. 批注记录保留在 `annotations.json`

## 7. draw.io 素材处理

素材中的 .drawio 文件:
1. 先尝试转换为 PNG: `python3 ${SKILL_DIR}/scripts/drawio_to_png.py --input xxx.drawio --output <dir>/`
2. 转换后的 PNG 纳入图表列表, 用户可在 Web 预览中查看
3. 如有修改需求, 告知用户需在 draw.io 中手动编辑
