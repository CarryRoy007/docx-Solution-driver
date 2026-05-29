#!/usr/bin/env python3
"""
环境依赖检测器 — 检测所有依赖, 分级报告, 提供 fallback 策略.
运行时机: skill 激活时自动运行, 或在脚本执行前运行.
"""

import sys
import os
import json
import shutil
import subprocess
from pathlib import Path


def check_python():
    version = sys.version_info
    ok = version >= (3, 9)
    return {
        "name": "Python",
        "required": ">=3.9",
        "current": f"{version.major}.{version.minor}.{version.micro}",
        "ok": ok,
        "fallback": "需要 Python >= 3.9, 请升级后重试" if not ok else None,
        "critical": not ok
    }


def check_pip_package(import_name, pip_name=None, description=""):
    pip_name = pip_name or import_name
    try:
        __import__(import_name)
        return {
            "name": pip_name,
            "description": description,
            "ok": True
        }
    except ImportError:
        return {
            "name": pip_name,
            "description": description,
            "ok": False,
            "install_cmd": f"pip install {pip_name}",
            "impact": _assess_impact(pip_name),
            "critical": pip_name in ("flask", "python-docx")
        }


def _assess_impact(pkg):
    impacts = {
        "flask": "Web 预览服务不可用, 仍可通过聊天交互",
        "python-docx": "无法生成 .docx 文件, 只能输出 Markdown",
        "python-pptx": "无法解析 PPT 素材文件",
        "Pillow": "无法处理图片, 图片提取和转换受限",
        "beautifulsoup4": "无法解析 HTML 素材",
        "lxml": "XML 解析能力受限, draw.io 转换可能失败",
        "cairosvg": "SVG → PNG 渲染不可用, 改用浏览器截图方式",
        "PyMuPDF": "无法解析 PDF 素材",
        "requests": "无法下载网络素材",
        "openpyxl": "无法解析 Excel 素材",
    }
    return impacts.get(pkg, "功能受限")


def check_system_tool(command, name, description="", macos_app_paths=None, install_guide=""):
    path = shutil.which(command)
    if not path and macos_app_paths:
        for app_path in macos_app_paths:
            if os.path.exists(app_path):
                path = app_path
                break
    return {
        "name": name,
        "description": description,
        "ok": path is not None,
        "path": str(path) if path else None,
        "fallback": _tool_fallback_v2(name),
        "install_guide": install_guide if not path else "",
        "critical": False
    }


def _tool_fallback_v2(name):
    fallbacks = {
        "drawio": {
            "impact": "无法将 .drawio 文件直接导出为 PNG",
            "fallback": "将使用内置 XML 解析器提取 draw.io 中的文本和结构",
            "install": "brew install --cask draw.io   # macOS\n或下载: https://github.com/jgraph/drawio-desktop/releases"
        },
        "libreoffice": {
            "impact": "无法将 .docx 转为 PDF 进行格式巡检",
            "fallback": "不影响 .docx 生成, 仅跳过格式验证步骤",
            "install": "brew install --cask libreoffice   # macOS\n或下载: https://www.libreoffice.org/download/"
        },
    }
    return fallbacks.get(name, {})


def check_write_permissions(base_dir):
    dirs_to_check = [base_dir]
    for d in dirs_to_check:
        if not os.path.exists(d):
            try:
                os.makedirs(d, exist_ok=True)
            except PermissionError:
                return {"name": "文件写入权限", "ok": False, "critical": True, "fallback": f"无权限写入 {d}"}
        elif not os.access(d, os.W_OK):
            return {"name": "文件写入权限", "ok": False, "critical": True, "fallback": f"无权限写入 {d}"}
    return {"name": "文件写入权限", "ok": True}


def run_full_check(base_dir="."):
    results = []

    results.append(check_python())

    packages = [
        ("flask", None, "Web 服务框架"),
        ("docx", "python-docx", "Word 文档生成"),
        ("pptx", "python-pptx", "PPT 文件解析"),
        ("PIL", "Pillow", "图片处理"),
        ("bs4", "beautifulsoup4", "HTML 解析"),
        ("lxml", None, "XML 解析"),
        ("cairosvg", None, "SVG → PNG 渲染"),
        ("fitz", "PyMuPDF", "PDF 解析"),
        ("requests", None, "HTTP 请求"),
        ("openpyxl", None, "Excel 解析"),
    ]

    for import_name, pip_name, desc in packages:
        results.append(check_pip_package(import_name, pip_name, desc))

    results.append(check_system_tool(
        "drawio", "draw.io Desktop",
        "用于将 .drawio 文件导出为 PNG/PDF（需单独下载安装）",
        macos_app_paths=["/Applications/draw.io.app/Contents/MacOS/draw.io"],
        install_guide="brew install --cask draw.io   # macOS\n或 https://github.com/jgraph/drawio-desktop/releases"
    ))
    results.append(check_system_tool(
        "soffice", "LibreOffice",
        "用于将 .docx 转为 PDF 进行格式巡检",
        macos_app_paths=["/Applications/LibreOffice.app/Contents/MacOS/soffice"],
        install_guide="brew install --cask libreoffice   # macOS\n或 https://www.libreoffice.org/download/"
    ))

    results.append(check_write_permissions(base_dir))

    return summarize(results)


def summarize(results):
    total = len(results)
    ok_count = sum(1 for r in results if r.get("ok"))
    critical_fails = [r for r in results if r.get("critical") and not r.get("ok")]
    warnings = [r for r in results if not r.get("critical") and not r.get("ok")]

    capacity = "full" if not critical_fails else "degraded" if len(critical_fails) < 2 else "minimal"

    return {
        "capacity": capacity,
        "total_checks": total,
        "passed": ok_count,
        "failed": total - ok_count,
        "critical_failures": critical_fails,
        "warnings": warnings,
        "all_checks": results,
        "summary_text": _build_summary_text(results, critical_fails, warnings)
    }


def _build_summary_text(results, critical_fails, warnings):
    lines = ["环境检测报告", "=" * 40, ""]

    for r in results:
        icon = "OK" if r.get("ok") else "FAIL" if r.get("critical") else "WARN"
        current = r.get('current', r.get('path', 'ok' if r.get('ok') else 'MISSING'))
        lines.append(f"[{icon}] {r['name']}: {current}")
        if r.get("description") and not r.get("ok"):
            lines.append(f"      用途: {r['description']}")
        fb = r.get("fallback", {})
        if fb:
            if fb.get("impact"):
                lines.append(f"      影响: {fb['impact']}")
            if fb.get("fallback"):
                lines.append(f"      回退: {fb['fallback']}")
            if fb.get("install"):
                lines.append(f"      安装: {fb['install']}")
        if r.get("install_guide"):
            lines.append(f"      安装: {r['install_guide']}")

    lines.append("")
    if not critical_fails and not warnings:
        lines.append("全部依赖就绪, 可正常使用全部功能。")
    elif critical_fails:
        missing = ', '.join(r['name'] for r in critical_fails)
        lines.append(f"关键依赖缺失: {missing}")
        lines.append(f"  → 安装命令: pip install {' '.join(r.get('install_cmd', '').replace('pip install ', '') for r in critical_fails)}")
        lines.append("  在关键依赖就绪前, 仅可使用基础 Markdown 写作功能。")
    else:
        lines.append(f"{len(warnings)} 个可选依赖未安装, 部分功能降级运行。")

    return '\n'.join(lines)


def generate_bootstrap_script(results, output_path):
    """生成自动修复脚本"""
    lines = ["#!/bin/bash", "# solution-docx 依赖自动修复脚本", "# 自动生成, 请检查后执行", ""]
    for r in results.get("all_checks", []):
        if not r.get("ok") and r.get("install_cmd"):
            lines.append(f"# {r.get('name')}: {r.get('description', '')}")
            lines.append(f"{r['install_cmd']}")
            lines.append("")
    lines.append("echo '依赖修复完成'")
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines))
    os.chmod(output_path, 0o755)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="solution-docx 环境依赖检测")
    parser.add_argument("--base-dir", default=".", help="基础工作目录")
    parser.add_argument("--output", default=None, help="结果输出路径 (JSON)")
    parser.add_argument("--bootstrap", default=None, help="生成自动修复脚本")
    parser.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    args = parser.parse_args()

    result = run_full_check(args.base_dir)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["summary_text"])

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    if args.bootstrap:
        generate_bootstrap_script(result, args.bootstrap)
        print(f"\n自动修复脚本: {args.bootstrap}")

    sys.exit(0 if result["capacity"] == "full" else 1)


if __name__ == "__main__":
    main()
