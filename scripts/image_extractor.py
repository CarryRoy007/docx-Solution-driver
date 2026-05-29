#!/usr/bin/env python3
"""图片提取器 — 从 PPT/DOCX/HTML 提取内嵌图片为 PNG."""

import json
import os
import sys
import argparse
import hashlib
from pathlib import Path
from io import BytesIO

try:
    from pptx import Presentation
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
    from bs4 import BeautifulSoup
    import requests
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

from PIL import Image


def extract_from_pptx(filepath, output_dir):
    if not HAS_PPTX:
        return {"error": "python-pptx not installed", "count": 0}
    prs = Presentation(filepath)
    extracted = []
    os.makedirs(output_dir, exist_ok=True)
    for i, slide in enumerate(prs.slides):
        for j, shape in enumerate(slide.shapes):
            if shape.shape_type == 13 and hasattr(shape, 'image'):
                image = shape.image
                ext = image.content_type.split('/')[-1]
                if ext == 'jpeg':
                    ext = 'jpg'
                fname = f"slide{i+1:02d}_img{j+1:02d}.{ext}"
                fpath = os.path.join(output_dir, fname)
                with open(fpath, 'wb') as f:
                    f.write(image.blob)
                extracted.append({
                    "source": str(filepath),
                    "slide": i + 1,
                    "shape": j + 1,
                    "filename": fname,
                    "format": ext,
                    "size": len(image.blob)
                })
    return {"source": str(filepath), "type": "pptx", "extracted": extracted, "count": len(extracted)}


def extract_from_docx(filepath, output_dir):
    if not HAS_DOCX:
        return {"error": "python-docx not installed", "count": 0}
    document = docx.Document(filepath)
    extracted = []
    os.makedirs(output_dir, exist_ok=True)
    for rel in document.part.rels.values():
        if "image" in rel.reltype:
            image = rel.target_part
            ext = image.content_type.split('/')[-1]
            if ext == 'jpeg':
                ext = 'jpg'
            fname = f"docx_img_{len(extracted)+1:03d}.{ext}"
            fpath = os.path.join(output_dir, fname)
            with open(fpath, 'wb') as f:
                f.write(image.blob)
            extracted.append({
                "source": str(filepath),
                "filename": fname,
                "format": ext,
                "size": len(image.blob)
            })
    return {"source": str(filepath), "type": "docx", "extracted": extracted, "count": len(extracted)}


def extract_from_html(filepath, output_dir):
    if not HAS_BS4:
        return {"error": "beautifulsoup4 not installed", "count": 0}
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        soup = BeautifulSoup(f.read(), 'lxml')
    extracted = []
    os.makedirs(output_dir, exist_ok=True)
    base_dir = Path(filepath).parent
    for i, img in enumerate(soup.find_all('img')):
        src = img.get('src', '')
        if not src:
            continue
        try:
            if src.startswith('http'):
                resp = requests.get(src, timeout=10)
                if resp.status_code == 200:
                    content = resp.content
                    img_format = src.split('.')[-1].split('?')[0].lower()
                    if img_format not in ('png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'):
                        img_format = 'png'
                else:
                    continue
            else:
                img_path = base_dir / src
                if not img_path.exists():
                    continue
                with open(img_path, 'rb') as f:
                    content = f.read()
                img_format = img_path.suffix.lstrip('.').lower()
            fname = f"html_img_{i+1:03d}.{img_format}"
            fpath = os.path.join(output_dir, fname)
            with open(fpath, 'wb') as f:
                f.write(content)
            extracted.append({
                "source": str(filepath),
                "src": src,
                "filename": fname,
                "format": img_format,
                "alt": img.get('alt', ''),
                "index": i + 1
            })
        except Exception as e:
            print(f"提取图片失败 {src}: {e}", file=sys.stderr)
    return {"source": str(filepath), "type": "html", "extracted": extracted, "count": len(extracted)}


def convert_to_png(filepath):
    try:
        img = Image.open(filepath)
        png_path = str(Path(filepath).with_suffix('.png'))
        if img.format == 'PNG' and filepath.endswith('.png'):
            return filepath
        img = img.convert('RGBA')
        img.save(png_path, 'PNG')
        return png_path
    except Exception as e:
        print(f"转换PNG失败 {filepath}: {e}", file=sys.stderr)
        return filepath


EXTRACTORS = {
    '.pptx': extract_from_pptx,
    '.ppt': extract_from_pptx,
    '.pptm': extract_from_pptx,
    '.docx': extract_from_docx,
    '.html': extract_from_html,
    '.htm': extract_from_html,
}


def main():
    parser = argparse.ArgumentParser(description="从文档中提取内嵌图片")
    parser.add_argument("--input", required=True, help="源文件路径")
    parser.add_argument("--output", default=".", help="输出目录")
    parser.add_argument("--convert-png", action="store_true", help="非PNG图片自动转换为PNG")
    args = parser.parse_args()

    ext = Path(args.input).suffix.lower()
    extractor = EXTRACTORS.get(ext)

    if not extractor:
        print(f"不支持的格式: {ext}")
        sys.exit(1)

    result = extractor(args.input, args.output)

    if args.convert_png and result.get('extracted'):
        for item in result['extracted']:
            fpath = os.path.join(args.output, item['filename'])
            if not fpath.endswith('.png'):
                png_path = convert_to_png(fpath)
                item['converted_to'] = os.path.basename(png_path)

    manifest_path = os.path.join(args.output, "image_manifest.json")
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"提取完成: {result['count']} 张图片")
    print(f"清单: {manifest_path}")


if __name__ == "__main__":
    main()
