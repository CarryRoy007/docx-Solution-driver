#!/usr/bin/env python3
"""
Web 预览服务 — 大纲编辑 + 图表批注.
双页面架构: /outline (大纲编辑) + /diagrams (图表批注), AI 按阶段自动切换.
"""

import json
import os
import sys
import signal
import threading
import time
import webbrowser
from pathlib import Path

try:
    from flask import Flask, request, jsonify, send_from_directory, render_template_string
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(SCRIPT_DIR, 'static')

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path='/static')

PROJECT_DIR = None
OUTLINE_PATH = None
DIAGRAMS_DIR = None
ANNOTATIONS_PATH = None
LOCK_FILE = None
LIVE_MODE = False
IDLE_TIMEOUT = 600
last_activity = time.time()
server_port = 5100


def check_inactivity():
    global last_activity
    while True:
        time.sleep(10)
        if LIVE_MODE and time.time() - last_activity > IDLE_TIMEOUT:
            print(f"\n空闲超时 ({IDLE_TIMEOUT}s), 自动关闭服务...")
            os._exit(0)


@app.before_request
def update_activity():
    global last_activity
    last_activity = time.time()


@app.route('/')
def index():
    return '<meta http-equiv="refresh" content="0;url=/outline">'


@app.route('/outline')
def outline_page():
    tmpl = os.path.join(STATIC_DIR, 'outline.html')
    if os.path.exists(tmpl):
        return send_from_directory(STATIC_DIR, 'outline.html')
    return _html_fallback('outline', '大纲编辑', 'outline.js')


@app.route('/diagrams')
def diagrams_page():
    tmpl = os.path.join(STATIC_DIR, 'diagram.html')
    if os.path.exists(tmpl):
        return send_from_directory(STATIC_DIR, 'diagram.html')
    return _html_fallback('diagram', '图表批注', 'diagram.js')


@app.route('/api/health')
def api_health():
    return jsonify({"status": "ok", "project": PROJECT_DIR})


CHECKPOINT_FILE = None


@app.route('/api/checkpoint', methods=['GET'])
def api_get_checkpoint():
    if CHECKPOINT_FILE and os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, 'r', encoding='utf-8') as f:
            return jsonify({"checkpoint": json.load(f)})
    return jsonify({"checkpoint": None, "phase": 0})


@app.route('/api/checkpoint', methods=['POST'])
def api_save_checkpoint():
    data = request.get_json(force=True)
    if CHECKPOINT_FILE:
        os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
        data['_timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
        with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "saved"})
    return jsonify({"error": "no checkpoint path"}), 400


@app.route('/api/status')
def api_status():
    status = {
        "project": PROJECT_DIR,
        "phases": {}
    }
    phases_dir = os.path.join(PROJECT_DIR, '00_analysis')
    status["phases"]["phase1_analysis"] = os.path.exists(os.path.join(phases_dir, 'material_analysis.json'))

    outline_path = os.path.join(PROJECT_DIR, '02_outline', 'outline.json')
    status["phases"]["phase2_outline"] = os.path.exists(outline_path)

    diagrams_path = os.path.join(PROJECT_DIR, '03_diagrams', 'sources')
    if os.path.exists(diagrams_path):
        svgs = len(list(Path(diagrams_path).glob('*.svg')))
        status["phases"]["phase4_diagrams"] = svgs
    else:
        status["phases"]["phase4_diagrams"] = 0

    drafts_path = os.path.join(PROJECT_DIR, '05_drafts')
    if os.path.exists(drafts_path):
        mds = len(list(Path(drafts_path).glob('*.md')))
        status["phases"]["phase5_draft"] = mds
    else:
        status["phases"]["phase5_draft"] = 0

    final_path = os.path.join(PROJECT_DIR, '06_final')
    if os.path.exists(final_path):
        docxs = len(list(Path(final_path).glob('*.docx')))
        status["phases"]["phase6_final"] = docxs
    else:
        status["phases"]["phase6_final"] = 0

    return jsonify(status)


@app.route('/api/config')
def api_config():
    return jsonify({
        "mode": "live" if LIVE_MODE else "standard",
        "project": PROJECT_DIR,
        "port": server_port
    })


@app.route('/api/outline', methods=['GET'])
def api_get_outline():
    if OUTLINE_PATH and os.path.exists(OUTLINE_PATH):
        with open(OUTLINE_PATH, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify([])


@app.route('/api/outline', methods=['POST'])
def api_save_outline():
    data = request.get_json(force=True)
    if OUTLINE_PATH:
        os.makedirs(os.path.dirname(OUTLINE_PATH), exist_ok=True)
        with open(OUTLINE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({"status": "saved", "path": OUTLINE_PATH})
    return jsonify({"error": "no outline path configured"}), 400


@app.route('/api/outline/md', methods=['GET'])
def api_outline_markdown():
    if OUTLINE_PATH and os.path.exists(OUTLINE_PATH):
        with open(OUTLINE_PATH, 'r', encoding='utf-8') as f:
            outline = json.load(f)
        md = _outline_to_md(outline)
        return jsonify({"markdown": md})
    return jsonify({"markdown": ""})


@app.route('/api/diagrams', methods=['GET'])
def api_list_diagrams():
    if not DIAGRAMS_DIR or not os.path.exists(DIAGRAMS_DIR):
        return jsonify([])

    sources_dir = os.path.join(DIAGRAMS_DIR, 'sources')
    png_dir = os.path.join(DIAGRAMS_DIR, 'png')

    diagrams = []
    svg_files = sorted(Path(sources_dir).glob('*.svg')) if os.path.exists(sources_dir) else []
    annotations = {}
    if ANNOTATIONS_PATH and os.path.exists(ANNOTATIONS_PATH):
        with open(ANNOTATIONS_PATH, 'r', encoding='utf-8') as f:
            annotations = json.load(f)

    for svg_file in svg_files:
        name = svg_file.stem
        png_file = os.path.join(png_dir, name + '.png')
        diagrams.append({
            "name": name,
            "has_png": os.path.exists(png_file),
            "annotation_count": len(annotations.get(name, []))
        })

    return jsonify(diagrams)


@app.route('/api/diagrams/<name>/svg', methods=['GET'])
def api_get_diagram_svg(name):
    svg_path = os.path.join(DIAGRAMS_DIR, 'sources', name + '.svg')
    if os.path.exists(svg_path):
        with open(svg_path, 'r', encoding='utf-8') as f:
            content = f.read()

        annotations = {}
        if ANNOTATIONS_PATH and os.path.exists(ANNOTATIONS_PATH):
            with open(ANNOTATIONS_PATH, 'r', encoding='utf-8') as f:
                annotations = json.load(f)

        elements = _parse_svg_elements(content)

        return jsonify({
            "name": name,
            "svg": content,
            "annotations": annotations.get(name, []),
            "elements": elements
        })
    return jsonify({"error": "not found"}), 404


@app.route('/api/diagrams/<name>/png', methods=['GET'])
def api_get_diagram_png(name):
    png_path = os.path.join(DIAGRAMS_DIR, 'png', name + '.png')
    if os.path.exists(png_path):
        return send_from_directory(os.path.join(DIAGRAMS_DIR, 'png'), name + '.png')
    return jsonify({"error": "PNG not found"}), 404


@app.route('/api/diagrams/<name>/svg', methods=['PUT'])
def api_update_diagram_svg(name):
    data = request.get_json(force=True)
    svg_content = data.get('svg', '')
    svg_path = os.path.join(DIAGRAMS_DIR, 'sources', name + '.svg')
    os.makedirs(os.path.dirname(svg_path), exist_ok=True)
    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write(svg_content)
    return jsonify({"status": "updated", "name": name})


@app.route('/api/diagrams/<name>/annotations', methods=['GET'])
def api_get_annotations(name):
    if ANNOTATIONS_PATH and os.path.exists(ANNOTATIONS_PATH):
        with open(ANNOTATIONS_PATH, 'r', encoding='utf-8') as f:
            all_ann = json.load(f)
        return jsonify(all_ann.get(name, []))
    return jsonify([])


@app.route('/api/diagrams/<name>/annotations', methods=['POST'])
def api_add_annotation(name):
    data = request.get_json(force=True)
    element_id = data.get('element_id', '')
    text = data.get('text', '')
    coords = data.get('coords', {})

    if not text:
        return jsonify({"error": "批注文本不能为空"}), 400

    os.makedirs(os.path.dirname(ANNOTATIONS_PATH) or '.', exist_ok=True)

    all_ann = {}
    if os.path.exists(ANNOTATIONS_PATH):
        with open(ANNOTATIONS_PATH, 'r', encoding='utf-8') as f:
            all_ann = json.load(f)

    if name not in all_ann:
        all_ann[name] = []

    annotation = {
        "id": f"ann_{int(time.time() * 1000)}",
        "element_id": element_id,
        "text": text,
        "coords": coords,
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    all_ann[name].append(annotation)

    with open(ANNOTATIONS_PATH, 'w', encoding='utf-8') as f:
        json.dump(all_ann, f, ensure_ascii=False, indent=2)

    return jsonify({"status": "added", "annotation": annotation})


@app.route('/api/diagrams/<name>/annotations/<ann_id>', methods=['DELETE'])
def api_delete_annotation(name, ann_id):
    if ANNOTATIONS_PATH and os.path.exists(ANNOTATIONS_PATH):
        with open(ANNOTATIONS_PATH, 'r', encoding='utf-8') as f:
            all_ann = json.load(f)
        if name in all_ann:
            all_ann[name] = [a for a in all_ann[name] if a.get('id') != ann_id]
        with open(ANNOTATIONS_PATH, 'w', encoding='utf-8') as f:
            json.dump(all_ann, f, ensure_ascii=False, indent=2)
    return jsonify({"status": "deleted"})


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    def shutdown():
        time.sleep(0.5)
        os._exit(0)

    t = threading.Thread(target=shutdown)
    t.daemon = True
    t.start()
    return jsonify({"status": "shutting_down"})


def _parse_svg_elements(svg_content):
    import re
    elements = []
    patterns = [
        (r'<rect[^>]*\bid="([^"]*)"', 'rect'),
        (r'<circle[^>]*\bid="([^"]*)"', 'circle'),
        (r'<ellipse[^>]*\bid="([^"]*)"', 'ellipse'),
        (r'<text[^>]*\bid="([^"]*)"', 'text'),
        (r'<g[^>]*\bid="([^"]*)"', 'group'),
        (r'<path[^>]*\bid="([^"]*)"', 'path'),
        (r'<line[^>]*\bid="([^"]*)"', 'line'),
        (r'<image[^>]*\bid="([^"]*)"', 'image'),
    ]
    for pattern, elem_type in patterns:
        for m in re.finditer(pattern, svg_content):
            elem_id = m.group(1) if m.lastindex else ''
            if elem_id:
                elements.append({"id": elem_id, "type": elem_type})
    return elements


def _outline_to_md(outline, prefix=''):
    lines = []
    for item in outline:
        hashes = '#' * min(item.get('level', 0) + 1, 6)
        num = item.get('number', '')
        text = item.get('text', '')
        lines.append(f"{hashes} {num} {text}")
        if item.get('children'):
            lines.extend(_outline_to_md(item['children'], prefix + '  '))
    return '\n'.join(lines)


def _html_fallback(page_id, title, js_file):
    return render_template_string('''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{{ title }} — solution-docx</title>
<link rel="stylesheet" href="/static/style.css">
</head>
<body class="{{ page_id }}-page">
  <div id="app">
    <div class="loading">加载中...</div>
  </div>
  <script src="/static/{{ js_file }}"></script>
</body>
</html>''', title=title, page_id=page_id, js_file=js_file)


def main():
    global PROJECT_DIR, OUTLINE_PATH, DIAGRAMS_DIR, ANNOTATIONS_PATH, CHECKPOINT_FILE
    global LIVE_MODE, server_port

    parser = __import__('argparse').ArgumentParser(description="solution-docx Web 预览服务")
    parser.add_argument("--project", required=True, help="项目目录")
    parser.add_argument("--port", type=int, default=5100, help="服务端口")
    parser.add_argument("--no-browser", action="store_true", help="不自动打开浏览器")
    parser.add_argument("--live", action="store_true", help="直播模式(空闲超时自动关闭)")
    args = parser.parse_args()

    if not HAS_FLASK:
        print("错误: Flask 未安装. 运行: pip install flask", file=sys.stderr)
        sys.exit(1)

    PROJECT_DIR = args.project
    server_port = args.port
    LIVE_MODE = args.live

    OUTLINE_PATH = os.path.join(PROJECT_DIR, '02_outline', 'outline.json')
    DIAGRAMS_DIR = os.path.join(PROJECT_DIR, '03_diagrams')
    ANNOTATIONS_PATH = os.path.join(DIAGRAMS_DIR, 'annotations.json')
    CHECKPOINT_FILE = os.path.join(PROJECT_DIR, '.checkpoint.json')

    if LIVE_MODE:
        t = threading.Thread(target=check_inactivity, daemon=True)
        t.start()

    if not args.no_browser:
        def open_browser():
            time.sleep(0.8)
            webbrowser.open(f'http://localhost:{server_port}')
        t = threading.Thread(target=open_browser)
        t.daemon = True
        t.start()

    print(f"solution-docx 预览服务")
    print(f"  项目: {PROJECT_DIR}")
    print(f"  地址: http://localhost:{server_port}")
    print(f"  大纲编辑: http://localhost:{server_port}/outline")
    print(f"  图表批注: http://localhost:{server_port}/diagrams")
    print(f"  按 Ctrl+C 停止服务\n")

    app.run(host='0.0.0.0', port=server_port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
