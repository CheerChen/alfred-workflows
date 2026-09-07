#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import os
import re
import hashlib

try:
    import fugashi
except ImportError:
    print(json.dumps({"items": [{
        "title": "fugashi 未安装",
        "subtitle": "请检查 Script Filter 中的 uv 命令是否正确"
    }]}))
    sys.exit(0)

# Cache config: readings never expire, same strategy as workflow-katakana
CACHE_DIR = os.getenv('alfred_workflow_data', os.path.expanduser('~/.alfred_workflow_data_furi'))
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

KANJI_RUN_RE = re.compile(r'[一-龯々〆]+')


def kata_to_hira(text):
    return ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in text)


def get_reading(token):
    # Unidic stores the dictionary reading in katakana; fall back to pronunciation
    kana = token.feature.kana or token.feature.pron
    return kata_to_hira(kana) if kana else None


def annotate_token(surface, reading):
    if not reading or not KANJI_RUN_RE.search(surface):
        return surface
    runs = list(KANJI_RUN_RE.finditer(surface))
    # Single kanji run: annotate only the kanji part, e.g. 傾き -> 傾(かたむ)き
    if len(runs) == 1:
        m = runs[0]
        pre, post = surface[:m.start()], surface[m.end():]
        if reading.startswith(pre) and reading.endswith(post) \
                and len(reading) > len(pre) + len(post):
            kanji_reading = reading[len(pre):len(reading) - len(post)]
            return f"{pre}{m.group()}({kanji_reading}){post}"
    return f"{surface}({reading})"


def convert(text):
    tagger = fugashi.Tagger()
    return ''.join(annotate_token(t.surface, get_reading(t)) for t in tagger(text))


def main(query):
    query = query.strip()
    if not query:
        print(json.dumps({"items": [{
            "title": "请输入日语单词或句子",
            "subtitle": "例: furi 傾きを測る"
        }]}))
        return

    cache_key = hashlib.md5(query.encode('utf-8')).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            furigana = json.load(f)['furigana']
    else:
        furigana = convert(query)
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump({"furigana": furigana}, f, ensure_ascii=False)

    items = [{
        "title": furigana,
        "subtitle": "Enter 复制 | ⌘+Enter 发音",
        "arg": furigana,
        "variables": {"tts_text": query},
        "text": {
            "copy": furigana,
            "largetype": furigana
        }
    }]

    # Per-token breakdown for tokens containing kanji
    tagger = fugashi.Tagger()
    for t in tagger(query):
        reading = get_reading(t)
        if KANJI_RUN_RE.search(t.surface) and reading:
            items.append({
                "title": annotate_token(t.surface, reading),
                "subtitle": "Enter 复制",
                "arg": annotate_token(t.surface, reading),
                "text": {
                    "copy": annotate_token(t.surface, reading),
                    "largetype": annotate_token(t.surface, reading)
                }
            })

    print(json.dumps({"items": items}))


if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print(json.dumps({"items": [{"title": "请输入日语单词或句子"}]}))
