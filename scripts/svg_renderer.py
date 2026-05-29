#!/usr/bin/env python3
"""SVG → PNG 渲染器 — 支持单个/批量转换，含中文字体检测."""

import os
import sys
import argparse
import subprocess
import json
from pathlib import Path
from io import BytesIO

try:
    import cairosvg
    HAS_CAIRO = True
except ImportError:
    HAS_CAIRO = False

try:
    from PIL import Image
    import numpy as np
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


CHINESE_FONT_STACK = (
    "PingFang SC, Heiti SC, Microsoft YaHei, "
    "Hiragino Sans GB, Songti SC, STHeiti, "
    "Arial Unicode MS, WenQuanYi Micro Hei, sans-serif"
)


def check_chinese_font_available():
    """
    检测系统是否能正确渲染中文字体。
    返回 (available: bool, detail: str)
    """
    if not HAS_CAIRO or not HAS_PIL:
        return False, "cairosvg 或 Pillow 未安装，无法检测"

    test_svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="300" height="70">
<rect width="300" height="70" fill="white"/>
<text x="10" y="45" font-family="{CHINESE_FONT_STACK}" font-size="36" fill="black">测试中文</text>
</svg>'''

    try:
        png_bytes = cairosvg.svg2png(bytestring=test_svg.encode())
        img = Image.open(BytesIO(png_bytes)).convert('L')
        arr = np.array(img)

        ink = arr < 200
        if ink.sum() < 20:
            return False, "渲染结果几乎无墨迹，字体可能未找到"

        ink_pixels = arr[ink]
        edge_count = 0
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            shifted = np.roll(ink, dy, axis=0)
            shifted = np.roll(shifted, dx, axis=1)
            edge_count += (ink & (~shifted)).sum()

        complexity = edge_count / max(ink.sum(), 1)

        if complexity < 0.2:
            return False, (
                f"字形复杂度过低 (complexity={complexity:.2f})，"
                "大概率是方框/豆腐块。中文字体不可用"
            )

        return True, f"中文字体渲染正常 (complexity={complexity:.2f})"

    except Exception as e:
        return False, f"检测异常: {e}"


def scan_svg_for_chinese(svg_path):
    """扫描 SVG 文件中是否包含中文字符."""
    try:
        with open(svg_path, 'r', encoding='utf-8') as f:
            content = f.read()
        chinese_chars = set()
        for ch in content:
            if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf':
                chinese_chars.add(ch)
        return len(chinese_chars) > 0, list(chinese_chars)[:20]
    except Exception:
        return False, []


def find_system_chinese_fonts():
    """查找系统中已安装的中文字体."""
    fonts = []
    try:
        result = subprocess.run(['fc-list', ':lang=zh'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    name = line.split(':')[0].strip()
                    if name not in fonts:
                        fonts.append(name)
    except Exception:
        pass
    return fonts


def generate_font_report(svg_path):
    """生成字体检测报告."""
    has_chinese, samples = scan_svg_for_chinese(svg_path)
    if not has_chinese:
        return {"status": "no_chinese", "message": "SVG 中无中文字符，无需检测"}

    system_fonts = find_system_chinese_fonts()
    font_ok, detail = check_chinese_font_available()

    return {
        "status": "ok" if font_ok else "tofu_risk",
        "message": detail,
        "chinese_chars_found": len(samples),
        "system_chinese_fonts": system_fonts[:10],
        "font_stack_used": CHINESE_FONT_STACK
    }


def render_svg_to_png(svg_path, png_path, scale=2):
    if not HAS_CAIRO:
        raise RuntimeError("cairosvg not installed. Run: pip install cairosvg")
    try:
        cairosvg.svg2png(url=svg_path, write_to=png_path, scale=scale)
        return True, png_path
    except Exception as e:
        return False, str(e)


def batch_render(input_dir, output_dir, scale=2):
    results = []
    os.makedirs(output_dir, exist_ok=True)
    svg_files = sorted(Path(input_dir).glob("*.svg"))
    if not svg_files:
        return results
    for svg_file in svg_files:
        png_name = svg_file.stem + ".png"
        png_path = os.path.join(output_dir, png_name)
        success, msg = render_svg_to_png(str(svg_file), png_path, scale)
        results.append({
            "svg": str(svg_file),
            "png": png_path,
            "success": success,
            "message": msg
        })
    return results


def get_svg_size(svg_path):
    try:
        tree = None
        try:
            from lxml import etree
            tree = etree.parse(svg_path)
        except ImportError:
            import xml.etree.ElementTree as ET
            tree = ET.parse(svg_path)
        root = tree.getroot()
        w = root.get('width', '')
        h = root.get('height', '')
        viewBox = root.get('viewBox', '')
        result = {}
        if viewBox:
            parts = viewBox.split()
            if len(parts) == 4:
                result['viewBox_width'] = parts[2]
                result['viewBox_height'] = parts[3]
        if w:
            result['width'] = w
        if h:
            result['height'] = h
        return result
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser(description="SVG → PNG 渲染器 (含中文字体检测)")
    parser.add_argument("--input", required=True, help="SVG 文件或目录路径")
    parser.add_argument("--output", required=True, help="输出 PNG 路径或目录")
    parser.add_argument("--scale", type=int, default=2, help="缩放倍率 (默认2x)")
    parser.add_argument("--batch", action="store_true", help="批量模式")
    parser.add_argument("--verify-chinese", action="store_true",
                        help="在渲染前检测中文字体可用性并输出报告")
    parser.add_argument("--report-only", action="store_true",
                        help="仅输出字体检测报告，不渲染")
    args = parser.parse_args()

    if not HAS_CAIRO:
        print("错误: cairosvg 未安装. 运行: pip install cairosvg", file=sys.stderr)
        sys.exit(1)

    if args.verify_chinese or args.report_only:
        report = generate_font_report(args.input)
        if args.report_only:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print(f"中文字体检测: {report['status']}")
            print(f"  {report['message']}")
            if report.get('system_chinese_fonts'):
                print(f"  系统字体: {', '.join(report['system_chinese_fonts'][:5])}")
            if report['status'] == 'tofu_risk':
                print("  警告: 渲染后中文可能显示为方框。如有问题请运行:")
                print("    pip install cairosvg  # 确保最新版")
                print("  或将 SVG 中的中文替换为英文后重新渲染")
        if args.report_only:
            return

    if args.batch or os.path.isdir(args.input):
        results = batch_render(args.input, args.output, args.scale)
        success_count = sum(1 for r in results if r['success'])
        fail_count = len(results) - success_count
        print(f"批量渲染: {success_count} 成功, {fail_count} 失败")
        for r in results:
            if not r['success']:
                print(f"  失败: {r['svg']} -> {r['message']}", file=sys.stderr)
    else:
        os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)
        success, msg = render_svg_to_png(args.input, args.output, args.scale)
        if success:
            size_info = get_svg_size(args.input)
            print(f"渲染成功: {msg}")
            if size_info:
                print(f"尺寸: {size_info}")
        else:
            print(f"渲染失败: {msg}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
