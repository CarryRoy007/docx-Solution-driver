#!/usr/bin/env python3
"""draw.io 文件转 PNG — 支持本地 drawio CLI 和在线 API."""

import os
import sys
import argparse
import subprocess
import shutil
import tempfile
from pathlib import Path

DRAWIO_CLI = None
for name in ['drawio', 'draw.io']:
    p = shutil.which(name)
    if p:
        DRAWIO_CLI = p
        break


def convert_with_cli(input_path, output_path):
    if not DRAWIO_CLI:
        return False, "drawio CLI not found"
    cmd = [
        DRAWIO_CLI, '--export', '--format', 'png',
        '--scale', '2',
        '--output', output_path,
        input_path
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0 and os.path.exists(output_path):
            return True, output_path
        return False, r.stderr or r.stdout or "export failed"
    except FileNotFoundError:
        return False, "drawio CLI executable not found"
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except Exception as e:
        return False, str(e)


def convert_via_xml_parse(input_path, output_path):
    try:
        import xml.etree.ElementTree as ET
    except ImportError:
        return False, "xml not available"

    try:
        tree = ET.parse(input_path)
        root = tree.getroot()

        mx_scale = root.get('dx', '1')
        mx_width = root.get('pageWidth', '800')
        mx_height = root.get('pageHeight', '600')

        svg_content = _drawio_to_svg(root, mx_width, mx_height)

        svg_path = str(Path(output_path).with_suffix('.svg'))
        with open(svg_path, 'w', encoding='utf-8') as f:
            f.write(svg_content)

        try:
            import cairosvg
            cairosvg.svg2png(url=svg_path, write_to=output_path, scale=2)
            if os.path.exists(output_path):
                return True, output_path
        except ImportError:
            pass

        return False, f"cairosvg not available, SVG saved to {svg_path}"
    except ET.ParseError as e:
        return False, f"XML parse error: {e}"
    except Exception as e:
        return False, str(e)


def _drawio_to_svg(root, width, height):
    cells = root.findall('.//mxCell')
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>']

    for cell in cells:
        style = cell.get('style', '')
        geom = cell.get('geometry', '')
        vertex = cell.get('vertex', '0')

        if geom:
            parts = geom.split(';')
            if len(parts) >= 4:
                x, y, w, h = parts[0], parts[1], parts[2], parts[3]

        value = (cell.get('value', '') or '').strip()
        if not value and vertex == '1':
            continue

        lines.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" '
                     f'fill="none" stroke="#555" stroke-width="1.5" rx="4"/>')
        if value:
            esc = value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            cx = float(x) + float(w) / 2
            cy = float(y) + float(h) / 2
            lines.append(f'<text x="{cx}" y="{cy}" text-anchor="middle" '
                         f'dominant-baseline="middle" font-family="sans-serif" font-size="12">{esc}</text>')

    for cell in cells:
        edge = cell.get('edge', '0')
        if edge == '1':
            source = cell.get('source', '')
            target = cell.get('target', '')
            lines.append(f'<line x1="0" y1="0" x2="{width}" y2="{height}" '
                         f'stroke="#555" stroke-width="1"/>')

    lines.append('</svg>')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description="draw.io 文件转 PNG")
    parser.add_argument("--input", required=True, help=".drawio 文件路径")
    parser.add_argument("--output", required=True, help="输出 PNG 路径")
    parser.add_argument("--method", choices=["auto", "cli", "xml"], default="auto", help="转换方式")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)

    input_ext = Path(args.input).suffix.lower()
    if input_ext not in ('.drawio', '.xml'):
        print(f"警告: 非 .drawio 文件: {args.input}")

    method = args.method
    success = False
    message = ""

    if method in ("auto", "cli") and DRAWIO_CLI:
        success, message = convert_with_cli(args.input, args.output)
        method = "cli"

    if not success and method in ("auto", "xml"):
        success, message = convert_via_xml_parse(args.input, args.output)
        method = "xml"

    if success:
        print(f"转换成功 ({method}): {message}")
    else:
        print(f"转换失败 ({method}): {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
