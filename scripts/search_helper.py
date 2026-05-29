#!/usr/bin/env python3
"""结构化搜索辅助 — 执行多关键词搜索并过滤低质量结果."""

import json
import os
import sys
import argparse
import re
from pathlib import Path
from urllib.parse import quote


QUALITY_PATTERNS = {
    "高": [
        r'gov\.cn', r'\.edu\.cn', r'std\.gov', r'全国标准', r'国家标准',
        r'白皮书', r'行业报告', r'信通院', r'工信部', r'发改委',
        r'scholar\.google', r'doi\.org', r'cnki\.net',
        r'\.arxiv\.org', r'ieee\.org', r'acm\.org'
    ],
    "中": [
        r'csdn\.net', r'zhihu\.com', r'jianshu\.com',
        r'人人都是产品经理', r'woshipm\.com',
        r'infoq\.com', r'oschina\.net', r'segmentfault\.com'
    ],
    "低": [
        r'广告', r'推广', r'促销', r'限时', r'震惊', r'竟然', r'必须看',
        r'看完就', r'干货满满', r'你绝对', r'万万没想到'
    ]
}


def assess_quality(url, snippet):
    score = 0
    combined = f"{url} {snippet}".lower()

    for pattern in QUALITY_PATTERNS["高"]:
        if re.search(pattern, combined, re.IGNORECASE):
            score += 3
    for pattern in QUALITY_PATTERNS["中"]:
        if re.search(pattern, combined, re.IGNORECASE):
            score += 1
    for pattern in QUALITY_PATTERNS["低"]:
        if re.search(pattern, combined, re.IGNORECASE):
            score -= 2

    if score >= 6:
        return "高"
    elif score >= 2:
        return "中"
    else:
        return "低"


def summarize_top(results, top_n=5):
    scored = []
    for r in results:
        url = r.get('url', '')
        snippet = r.get('snippet', '')
        quality = assess_quality(url, snippet)
        scored.append({**r, 'quality': quality})

    scored.sort(key=lambda x: (
        0 if x['quality'] == '高' else (1 if x['quality'] == '中' else 2),
        -len(str(x.get('snippet', '')))
    ))

    return scored[:top_n]


def main():
    parser = argparse.ArgumentParser(description="结构化搜索辅助")
    parser.add_argument("--queries", nargs="+", required=True, help="搜索关键词列表")
    parser.add_argument("--output", default=".", help="输出目录")
    parser.add_argument("--max-results", type=int, default=10, help="每个关键词返回数量")
    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    search_params = []
    for query in args.queries:
        encoded = quote(query)
        url = f"https://www.google.com/search?q={encoded}&num={args.max_results}"
        search_params.append({
            "query": query,
            "search_url": url,
            "max_results": args.max_results
        })

    report = {
        "queries": args.queries,
        "search_urls": search_params,
        "note": "在 opencode 环境中, 使用 anysearch_search 执行实际搜索."
                "本脚本输出搜索参数供 AI 调度使用."
    }

    json_path = os.path.join(args.output, "search_plan.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"搜索计划已生成: {json_path}")
    print("请在 opencode 中执行:")
    for sp in search_params:
        print(f"  anysearch_search(query=\"{sp['query']}\", max_results={sp['max_results']})")


if __name__ == "__main__":
    main()
