#!/usr/bin/env python3
"""用户模板 .docx 全自动深度分析 — 封面/标题/正文/页边距/页眉页脚."""

import json
import os
import sys
import argparse
from pathlib import Path

try:
    import docx
    from docx.shared import Pt, Inches, Cm, Emu
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False


def emu_to_cm(emu):
    return round(emu / 360000 * 2.54, 2) if emu else None


def emu_to_pt(emu):
    return round(emu / 12700, 1) if emu else None


def get_run_font(run):
    font = {}
    rpr = run._element.find(qn('w:rPr'))
    if rpr is None:
        return font
    sz = rpr.find(qn('w:sz'))
    if sz is not None:
        font['size_pt'] = emu_to_pt(int(sz.get(qn('w:val'), 0)) * 100)
    sz_cs = rpr.find(qn('w:szCs'))
    if sz_cs is not None and 'size_pt' not in font:
        font['size_pt'] = emu_to_pt(int(sz_cs.get(qn('w:val'), 0)) * 100)
    for tag, key in [(qn('w:rFonts'), 'fonts'), (qn('w:b'), 'bold'), (qn('w:i'), 'italic')]:
        el = rpr.find(tag)
        if el is not None:
            if key == 'fonts':
                font['font_east'] = el.get(qn('w:eastAsia'), '') or el.get(qn('w:ascii'), '')
                font['font_west'] = el.get(qn('w:ascii'), '')
            elif key == 'bold':
                font['bold'] = el.get(qn('w:val'), '1') != '0'
            elif key == 'italic':
                font['italic'] = el.get(qn('w:val'), '1') != '0'
    return font


def get_para_style(para):
    info = {}
    ppr = para._element.find(qn('w:pPr'))
    if ppr is None:
        return info

    jc = ppr.find(qn('w:jc'))
    if jc is not None:
        align_map = {'left': '左对齐', 'center': '居中', 'right': '右对齐', 'both': '两端对齐'}
        info['align'] = align_map.get(jc.get(qn('w:val'), ''), jc.get(qn('w:val'), ''))

    outline_lvl = ppr.find(qn('w:outlineLvl'))
    if outline_lvl is not None:
        info['outline_level'] = int(outline_lvl.get(qn('w:val'), '0'))

    spacing = ppr.find(qn('w:spacing'))
    if spacing is not None:
        before = spacing.get(qn('w:before'))
        after = spacing.get(qn('w:after'))
        line = spacing.get(qn('w:line'))
        if before:
            info['spacing_before_pt'] = emu_to_pt(int(before))
        if after:
            info['spacing_after_pt'] = emu_to_pt(int(after))
        if line:
            info['line_spacing'] = round(int(line) / 240, 2)

    ind = ppr.find(qn('w:ind'))
    if ind is not None:
        first = ind.get(qn('w:firstLine'))
        if first:
            info['first_line_indent_pt'] = emu_to_pt(int(first))

    return info


def get_section_info(section):
    info = {}
    pg_sz = section._sectPr.find(qn('w:pgSz'))
    if pg_sz is not None:
        w = pg_sz.get(qn('w:w'))
        h = pg_sz.get(qn('w:h'))
        info['page_size'] = f"{emu_to_cm(int(w))}x{emu_to_cm(int(h))}cm" if w and h else None

    pg_mar = section._sectPr.find(qn('w:pgMar'))
    if pg_mar is not None:
        info['margin_top_cm'] = emu_to_cm(int(pg_mar.get(qn('w:top'), 0)))
        info['margin_bottom_cm'] = emu_to_cm(int(pg_mar.get(qn('w:bottom'), 0)))
        info['margin_left_cm'] = emu_to_cm(int(pg_mar.get(qn('w:left'), 0)))
        info['margin_right_cm'] = emu_to_cm(int(pg_mar.get(qn('w:right'), 0)))

    return info


def extract_cover_info(paragraphs, max_look=10):
    for i, p in enumerate(paragraphs[:max_look]):
        text = p.get("text", "")
        if len(text) > 5 and p.get("style", "") not in ["Normal", "normal", ""]:
            return {
                "cover_detected": True,
                "first_line": text[:100],
                "style_used": p.get("style", ""),
                "font": p.get("font", {}),
                "align": p.get("align", ""),
                "position": i
            }
    return {"cover_detected": False}


def analyze_headers_footers(document):
    hf_info = {"headers": [], "footers": []}
    for i, section in enumerate(document.sections):
        header = section.header
        footer = section.footer
        if header and not header.is_linked_to_previous:
            hf_info["headers"].append({
                "section": i,
                "text": header.paragraphs[0].text[:200] if header.paragraphs else ""
            })
        if footer and not footer.is_linked_to_previous:
            hf_info["footers"].append({
                "section": i,
                "text": footer.paragraphs[0].text[:200] if footer.paragraphs else ""
            })
    return hf_info


def analyze_template(filepath):
    if not HAS_DOCX:
        return {"error": "python-docx not installed"}

    doc = docx.Document(filepath)
    paragraphs = []
    heading_samples = {}
    body_samples = []
    image_count = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        font_info = {}
        if para.runs:
            font_info = get_run_font(para.runs[0])

        style_info = get_para_style(para)
        style_name = para.style.name if para.style else "Normal"
        outline_level = style_info.get('outline_level', 999)

        has_image = False
        for run in para.runs:
            for elem in run._element:
                if elem.tag.endswith('}drawing') or elem.tag.endswith('}pict'):
                    has_image = True

        if has_image:
            image_count += 1
            continue

        p_info = {
            "text": text[:200],
            "style": style_name,
            "font": font_info,
            "align": style_info.get('align', ''),
            "outline_level": outline_level,
            "spacing": {k: v for k, v in style_info.items() if k.startswith('spacing') or k.startswith('line')},
            "indent": style_info.get('first_line_indent_pt'),
            "index": len(paragraphs)
        }
        paragraphs.append(p_info)

        if outline_level == 0 or (outline_level == 999 and style_name.startswith('Heading')):
            level = outline_level if outline_level != 999 else int(style_name.replace('Heading', '').strip() or 1) - 1
            if level not in heading_samples:
                heading_samples[level] = []
            if len(heading_samples[level]) < 3:
                heading_samples[level].append(p_info)
        elif len(body_samples) < 3 and len(text) > 10:
            body_samples.append(p_info)

    sections_info = []
    for s in doc.sections:
        sections_info.append(get_section_info(s))

    cover = extract_cover_info(paragraphs)
    hf = analyze_headers_footers(doc)

    style_catalog = {}
    for p in paragraphs:
        style_name = p.get("style", "")
        if style_name not in style_catalog:
            style_catalog[style_name] = {
                "style": style_name,
                "font": p.get("font", {}),
                "align": p.get("align", ""),
                "outline_level": p.get("outline_level", 999),
                "spacing": p.get("spacing", {}),
                "indent": p.get("indent"),
                "count": 0
            }
        style_catalog[style_name]["count"] += 1

    heading_profile = {}
    for level in sorted(heading_samples.keys()):
        samples = heading_samples[level]
        fonts = [s.get('font', {}).get('size_pt') for s in samples if s.get('font', {}).get('size_pt')]
        heading_profile[f"level_{level}"] = {
            "level": level,
            "sample_count": len(samples),
            "avg_font_size": round(sum(fonts) / len(fonts), 1) if fonts else None,
            "font_east": samples[0].get('font', {}).get('font_east', '') if samples else '',
            "bold": samples[0].get('font', {}).get('bold') if samples else None,
            "align": samples[0].get('align', ''),
            "sample_text": [s.get('text', '')[:80] for s in samples[:3]]
        }

    completeness = {
        "has_cover": cover.get("cover_detected", False),
        "heading_levels_detected": len(heading_profile),
        "has_body_style": len(body_samples) > 0,
        "has_margins": bool(sections_info and sections_info[0].get('margin_top_cm')),
        "has_headers": len(hf.get('headers', [])) > 0,
        "has_footers": len(hf.get('footers', [])) > 0,
    }
    completeness["score"] = sum([
        15 if completeness["has_cover"] else 0,
        25 * min(completeness["heading_levels_detected"], 4) / 4,
        20 if completeness["has_body_style"] else 0,
        15 if completeness["has_margins"] else 0,
        10 if completeness["has_headers"] else 0,
        15 if completeness["has_footers"] else 0,
    ])
    completeness["rating"] = "优秀" if completeness["score"] >= 80 else "良好" if completeness["score"] >= 60 else "不足"

    return {
        "template_path": str(filepath),
        "paragraph_count": len(paragraphs),
        "image_count": image_count,
        "cover": cover,
        "heading_profile": heading_profile,
        "body_samples": body_samples[:5],
        "sections": sections_info,
        "headers_footers": hf,
        "style_catalog": {k: v for k, v in list(style_catalog.items())[:20]},
        "completeness": completeness,
        "deficiencies": _identify_deficiencies(completeness, heading_profile)
    }


def _identify_deficiencies(completeness, heading_profile):
    deficiencies = []
    if not completeness["has_cover"]:
        deficiencies.append("缺少封面样式")
    if completeness["heading_levels_detected"] < 3:
        deficiencies.append(f"仅检测到{completeness['heading_levels_detected']}级标题, 建议至少3级")
    if not completeness["has_body_style"]:
        deficiencies.append("未检测到正文段落样式")
    if not completeness["has_margins"]:
        deficiencies.append("未检测到页边距设置, 将使用默认值")
    if not completeness["has_footers"]:
        deficiencies.append("未检测到页脚(页码), 将自动添加")
    return deficiencies


def main():
    parser = argparse.ArgumentParser(description="深度分析 .docx 模板")
    parser.add_argument("template", help="模板 .docx 路径")
    parser.add_argument("--output", default=".", help="输出目录")
    args = parser.parse_args()

    result = analyze_template(args.template)
    os.makedirs(args.output, exist_ok=True)

    json_path = os.path.join(args.output, "template_profile.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    md_path = os.path.join(args.output, "template_profile.md")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# 模板分析报告: {Path(args.template).name}\n\n")
        f.write(f"**完整度**: {result['completeness']['score']:.0f}分 ({result['completeness']['rating']})\n\n")

        f.write("## 封面\n")
        f.write(f"- 检测到封面: {'是' if result['cover']['cover_detected'] else '否'}\n\n")

        f.write("## 标题层级\n")
        for level, info in sorted(result['heading_profile'].items()):
            f.write(f"- **{level}**: 字号 {info.get('avg_font_size', '?')}pt, ")
            f.write(f"字体 {info.get('font_east', '?')}, ")
            f.write(f"加粗: {info.get('bold', '?')}, ")
            f.write(f"对齐: {info.get('align', '?')}\n")
            for s in info.get('sample_text', []):
                f.write(f"  样例: {s}\n")

        f.write("\n## 正文\n")
        for b in result['body_samples'][:3]:
            f.write(f"- 字体: {b['font']}, 对齐: {b['align']}, ")
            f.write(f"缩进: {b.get('indent', '无')}pt\n")
            f.write(f"  文本: {b['text'][:100]}\n")

        f.write("\n## 页边距\n")
        if result['sections']:
            s = result['sections'][0]
            f.write(f"- 上: {s.get('margin_top_cm', '?')}cm, 下: {s.get('margin_bottom_cm', '?')}cm, ")
            f.write(f"左: {s.get('margin_left_cm', '?')}cm, 右: {s.get('margin_right_cm', '?')}cm\n")

        if result['deficiencies']:
            f.write("\n## 模板不足\n")
            for d in result['deficiencies']:
                f.write(f"- {d}\n")

    print(f"分析完成: 完整度 {result['completeness']['score']:.0f}分 ({result['completeness']['rating']})")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")


if __name__ == "__main__":
    main()
