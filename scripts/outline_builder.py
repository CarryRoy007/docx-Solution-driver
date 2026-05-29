#!/usr/bin/env python3
"""大纲构建器 — 大纲生成/编辑/序列化."""

import json
import os
import argparse
from pathlib import Path

SOLUTION_TEMPLATES = {
    "技术方案": {
        "一级标题": [
            "项目背景与目标",
            "需求分析",
            "技术架构设计",
            "实施方案",
            "项目管理与保障",
            "效益分析"
        ],
        "二级标题": {
            "项目背景与目标": ["政策背景", "行业现状与趋势", "建设必要性", "建设目标"],
            "需求分析": ["业务需求", "功能需求", "非功能性需求", "数据需求"],
            "技术架构设计": ["总体架构", "技术选型", "核心模块设计", "数据架构", "安全架构"],
            "实施方案": ["实施策略", "实施步骤", "部署方案", "人员配置", "培训计划"],
            "项目管理与保障": ["项目组织", "质量保障", "风险管控", "运维保障"],
            "效益分析": ["经济效益", "社会效益", "风险评估"]
        }
    },
    "可研报告": {
        "一级标题": [
            "项目概述",
            "建设必要性",
            "需求分析和规模预测",
            "建设方案",
            "项目实施与进度安排",
            "投资估算与资金筹措",
            "效益与风险分析",
            "结论与建议"
        ],
        "二级标题": {
            "项目概述": ["项目名称与基本信息", "项目建设单位", "报告编制依据", "项目概况"],
            "建设必要性": ["现状分析", "存在问题", "建设必要性论述"],
            "需求分析和规模预测": ["业务需求分析", "用户规模预测", "数据量估算"],
            "建设方案": ["总体方案", "技术架构", "设备选型", "安全方案"],
            "项目实施与进度安排": ["实施策略", "进度计划", "里程碑节点"],
            "投资估算与资金筹措": ["投资估算", "资金来源", "分期投入计划"],
            "效益与风险分析": ["经济效益", "社会效益", "风险识别与对策"],
            "结论与建议": ["主要结论", "建议"]
        }
    },
    "解决方案": {
        "一级标题": [
            "项目概述",
            "需求理解与分析",
            "解决方案设计",
            "实施规划",
            "服务与保障",
            "成功案例"
        ],
        "二级标题": {
            "项目概述": ["背景", "目标", "范围"],
            "需求理解与分析": ["业务痛洞察", "需求总结", "关键技术要求"],
            "解决方案设计": ["总体方案", "技术架构", "功能模块", "部署方案"],
            "实施规划": ["实施路线图", "资源需求", "时间计划"],
            "服务与保障": ["运维服务", "技术支持", "培训服务"],
            "成功案例": ["案例一", "案例二"]
        }
    }
}


def generate_outline(doc_type, num_levels=3):
    template = SOLUTION_TEMPLATES.get(doc_type, SOLUTION_TEMPLATES["技术方案"])
    outline = []
    for i, h1_text in enumerate(template["一级标题"]):
        h1 = {
            "id": f"h1_{i+1}",
            "level": 1,
            "number": f"{_to_chinese_num(i+1)}、",
            "text": h1_text,
            "children": []
        }
        subs = template.get("二级标题", {}).get(h1_text, [])
        for j, h2_text in enumerate(subs):
            h2 = {
                "id": f"h1_{i+1}_h2_{j+1}",
                "level": 2,
                "number": f"{i+1}.{j+1}",
                "text": h2_text,
                "children": []
            }
            if num_levels >= 3:
                h2["children"].append({
                    "id": f"h1_{i+1}_h2_{j+1}_h3_1",
                    "level": 3,
                    "number": f"({j+1})",
                    "text": "(待填充)",
                    "children": [],
                    "placeholder": True
                })
            h1["children"].append(h2)
        outline.append(h1)
    return outline


def _to_chinese_num(n):
    nums = ['', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十',
            '十一', '十二', '十三', '十四', '十五', '十六', '十七', '十八', '十九', '二十']
    if 1 <= n <= 20:
        return nums[n]
    return str(n)


def outline_to_markdown(outline, indent=0):
    lines = []
    for item in outline:
        prefix = "#" * min(item["level"] + 1, 6)
        lines.append(f"{prefix} {item['number']} {item['text']}")
        if item.get("children"):
            lines.append(outline_to_markdown(item["children"], indent + 1))
    return "\n".join(lines)


def serialize_outline(outline, filepath):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(outline, f, ensure_ascii=False, indent=2)


def deserialize_outline(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="大纲生成与编辑工具")
    parser.add_argument("--type", default="技术方案", choices=list(SOLUTION_TEMPLATES.keys()), help="文档类型")
    parser.add_argument("--levels", type=int, default=3, help="大纲层级")
    parser.add_argument("--output", default=".", help="输出目录")
    parser.add_argument("--to-md", action="store_true", help="同时输出Markdown格式")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)
    outline = generate_outline(args.type, args.levels)

    json_path = os.path.join(args.output, "outline.json")
    serialize_outline(outline, json_path)
    print(f"大纲已保存: {json_path}")

    if args.to_md:
        md_path = os.path.join(args.output, "outline.md")
        md_content = outline_to_markdown(outline)
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
