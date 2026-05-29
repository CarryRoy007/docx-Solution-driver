#!/usr/bin/env python3
"""素材分析引擎 — 解析 PPT/DOCX/HTML/draw.io/PDF/图片/URL, 输出结构化分析报告."""

import json
import os
import re
import sys
import argparse
import hashlib
from pathlib import Path
from collections import defaultdict
from html.parser import HTMLParser

try:
    from pptx import Presentation
    from pptx.util import Inches, Pt
    HAS_PPTX = True
except ImportError:
    HAS_PPTX = False

try:
    import docx
    from docx.opc.constants import RELATIONSHIP_TYPE as RT
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

try:
    import fitz
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

from PIL import Image

SUPPORTED_IMAGE_EXT = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.svg'}
SUPPORTED_DRAWIO_EXT = {'.drawio', '.xml'}
SUPPORTED_HTML_EXT = {'.html', '.htm'}


def hash_content(data):
    return hashlib.md5(data if isinstance(data, bytes) else data.encode()).hexdigest()[:12]


def analyze_pptx(filepath):
    if not HAS_PPTX:
        return {"error": "python-pptx not installed", "slides": 0}
    prs = Presentation(filepath)
    slides_info = []
    image_count = 0
    for i, slide in enumerate(prs.slides):
        texts = []
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        for shape in slide.shapes:
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    t = paragraph.text.strip()
                    if t:
                        texts.append(t)
            if shape.shape_type == 13:
                image_count += 1
        slides_info.append({
            "index": i + 1,
            "text": "\n".join(texts),
            "text_length": len("\n".join(texts)),
            "has_notes": bool(notes),
            "notes": notes[:200] if notes else ""
        })
    return {
        "type": "pptx",
        "path": str(filepath),
        "slides": len(slides_info),
        "image_count": image_count,
        "slides_info": slides_info
    }


def analyze_docx(filepath):
    if not HAS_DOCX:
        return {"error": "python-docx not installed"}
    document = docx.Document(filepath)
    paragraphs = []
    image_count = 0
    image_captions = []
    prev_text = ""
    for para in document.paragraphs:
        text = para.text.strip()
        style = para.style.name if para.style else "Normal"
        if not text:
            continue
        has_image = False
        for run in para.runs:
            for elem in run._element:
                if elem.tag.endswith('}drawing') or elem.tag.endswith('}pict'):
                    has_image = True
                    break
        if has_image:
            image_count += 1
            if prev_text:
                image_captions.append({"caption": prev_text, "image_index": image_count})
        else:
            paragraphs.append({
                "text": text[:500],
                "style": style,
                "level": para.paragraph_format.outline_level if para.paragraph_format.outline_level else 0
            })
            prev_text = text
    return {
        "type": "docx",
        "path": str(filepath),
        "paragraph_count": len(paragraphs),
        "image_count": image_count,
        "image_captions": image_captions,
        "paragraphs": paragraphs[:200]
    }


def analyze_html(filepath):
    if not HAS_BS4:
        return {"error": "beautifulsoup4 not installed"}
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    body = soup.find('body') or soup
    text = body.get_text(separator='\n', strip=True)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    images = []
    for img in soup.find_all('img'):
        src = img.get('src', '')
        alt = img.get('alt', '')
        images.append({"src": src, "alt": alt})
    return {
        "type": "html",
        "path": str(filepath),
        "text_lines": len(lines),
        "text_preview": '\n'.join(lines[:100]),
        "image_refs": images,
        "title": soup.title.string if soup.title else ""
    }


def analyze_pdf(filepath):
    if not HAS_PYMUPDF:
        return {"error": "PyMuPDF not installed"}
    doc = fitz.open(filepath)
    page_count = len(doc)
    text_samples = []
    image_count = 0
    for i in range(min(page_count, 30)):
        page = doc[i]
        text = page.get_text()
        if text.strip():
            text_samples.append(text.strip()[:300])
        images = page.get_images()
        image_count += len(images)
    doc.close()
    return {
        "type": "pdf",
        "path": str(filepath),
        "pages": page_count,
        "image_count": image_count,
        "text_samples": text_samples[:5]
    }


def analyze_image(filepath):
    try:
        img = Image.open(filepath)
        return {
            "type": "image",
            "path": str(filepath),
            "format": img.format,
            "size": f"{img.width}x{img.height}",
            "mode": img.mode
        }
    except Exception as e:
        return {"type": "image", "path": str(filepath), "error": str(e)}


def analyze_drawio(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return {
        "type": "drawio",
        "path": str(filepath),
        "size_bytes": len(content),
        "is_xml": content.strip().startswith('<?xml') or '<mxfile' in content
    }


def analyze_text(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    lines = [l.strip() for l in content.split('\n') if l.strip()]
    return {
        "type": "text",
        "path": str(filepath),
        "lines": len(lines),
        "preview": '\n'.join(lines[:50])
    }


ANALYZERS = {
    '.pptx': analyze_pptx,
    '.ppt': analyze_pptx,
    '.pptm': analyze_pptx,
    '.ppsx': analyze_pptx,
    '.docx': analyze_docx,
    '.doc': analyze_docx,
    '.html': analyze_html,
    '.htm': analyze_html,
    '.pdf': analyze_pdf,
    '.png': analyze_image,
    '.jpg': analyze_image,
    '.jpeg': analyze_image,
    '.gif': analyze_image,
    '.bmp': analyze_image,
    '.webp': analyze_image,
    '.svg': analyze_image,
    '.drawio': analyze_drawio,
    '.md': analyze_text,
    '.txt': analyze_text,
}


def analyze_file(filepath):
    ext = Path(filepath).suffix.lower()
    analyzer = ANALYZERS.get(ext)
    if analyzer:
        return analyzer(filepath)
    else:
        return {"type": "unknown", "path": str(filepath), "extension": ext}


def build_usage_summary(results_by_type):
    summary = {"total_files": 0, "by_type": {}, "total_images_found": 0, "total_image_captions": 0}
    for r in results_by_type.get("all", []):
        if isinstance(r, dict):
            summary["total_files"] += 1
            t = r.get("type", "unknown")
            summary["by_type"][t] = summary["by_type"].get(t, 0) + 1
            if "image_count" in r:
                summary["total_images_found"] += r["image_count"]
            if "image_captions" in r and r["image_captions"]:
                summary["total_image_captions"] += len(r["image_captions"])
    return summary


def main():
    parser = argparse.ArgumentParser(description="解析素材文件, 输出结构化分析报告")
    parser.add_argument("--inputs", nargs="+", required=True, help="素材路径列表(文件/目录)")
    parser.add_argument("--output", default=".", help="输出目录")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    all_files = []
    for input_path in args.inputs:
        p = Path(input_path)
        if p.is_dir():
            for ext in ANALYZERS:
                all_files.extend(p.rglob(f"*{ext}"))
            all_files.extend(p.rglob("*.xml"))
        elif p.is_file():
            all_files.append(p)
        else:
            print(f"警告: {input_path} 不存在或无法访问", file=sys.stderr)

    all_files = sorted(set(all_files), key=str)
    results = []
    errors = []

    for fp in all_files:
        try:
            r = analyze_file(str(fp))
            results.append(r)
        except Exception as e:
            errors.append({"path": str(fp), "error": str(e)})
            results.append({"type": "error", "path": str(fp), "error": str(e)})

    summary = build_usage_summary({"all": results})

    report = {
        "analysis_version": "1.0",
        "summary": summary,
        "results": results,
        "errors": errors
    }

    report_path = os.path.join(args.output, "material_analysis.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    markdown_path = os.path.join(args.output, "material_analysis.md")
    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(f"# 素材分析报告\n\n")
        f.write(f"**总计**: {summary['total_files']} 个文件\n\n")
        f.write("## 文件类型分布\n\n")
        for t, count in sorted(summary['by_type'].items()):
            f.write(f"- {t}: {count}\n")
        f.write(f"\n**发现图片**: {summary['total_images_found']} 张\n")
        f.write(f"**带图题图片**: {summary['total_image_captions']} 张\n\n")

        f.write("## 详细清单\n\n")
        for r in results:
            t = r.get("type", "unknown")
            path = r.get("path", "")
            f.write(f"### {Path(path).name}\n\n")
            f.write(f"- 类型: {t}\n")
            f.write(f"- 路径: {path}\n")
            if t == "pptx":
                f.write(f"- 幻灯片: {r.get('slides', 0)} 页\n")
                f.write(f"- 内嵌图片: {r.get('image_count', 0)} 张\n")
            elif t == "docx":
                f.write(f"- 段落: {r.get('paragraph_count', 0)}\n")
                f.write(f"- 内嵌图片: {r.get('image_count', 0)} 张\n")
                if r.get("image_captions"):
                    f.write(f"- 图片图题:\n")
                    for cap in r["image_captions"]:
                        f.write(f"  - {cap['caption']}\n")
            elif t == "image":
                f.write(f"- 格式: {r.get('format', '?')} | 尺寸: {r.get('size', '?')}\n")
            elif t == "drawio":
                f.write(f"- {r.get('size_bytes', 0)} bytes\n")
            elif t == "pdf":
                f.write(f"- 页数: {r.get('pages', 0)}\n")
            elif t == "text":
                f.write(f"- 行数: {r.get('lines', 0)}\n")
            f.write("\n")

    print(f"分析完成: {summary['total_files']} 个文件")
    print(f"JSON: {report_path}")
    print(f"Markdown: {markdown_path}")


if __name__ == "__main__":
    main()
