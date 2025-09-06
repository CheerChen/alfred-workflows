#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import urllib.parse
import urllib.request
from urllib.error import URLError
import re
import os
import time
import hashlib

# 缓存配置
# 缓存永不过期
CACHE_DIR = os.getenv('alfred_workflow_data', os.path.expanduser('~/.alfred_workflow_data_kata'))
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def jisho_search(word):
    """使用 Jisho API 搜索单词，带缓存功能"""
    # 创建缓存键
    cache_key = hashlib.md5(word.encode('utf-8')).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    
    # 检查缓存，永不过期
    if os.path.exists(cache_file):
        print(f"DEBUG: Loading from cache for '{word}'", file=sys.stderr)
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    try:
        url = "https://jisho.org/api/v1/search/words?keyword=" + urllib.parse.quote(word)
        
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )
        
        print(f"DEBUG: Fetching from Jisho API for '{word}'", file=sys.stderr)
        start_time = time.time()
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            result = json.loads(data)
            
            end_time = time.time()
            print(f"DEBUG: API request completed in {end_time - start_time:.3f} seconds", file=sys.stderr)
            
            if result and result.get('data'):
                # 保存到缓存
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result['data'], f, ensure_ascii=False, indent=2)
                return result['data']
                
        return None
        
    except Exception as e:
        print(f"Jisho API 错误: {str(e)}", file=sys.stderr)
        return None

def is_katakana_reading(reading):
    """检查读音是否主要是片假名"""
    if not reading:
        return False
    katakana_chars = len(re.findall(r'[\u30A1-\u30FA\u30FC-\u30FF]', reading))
    total_chars = len(re.sub(r'[・\s]', '', reading))  # 排除中点和空格
    return katakana_chars / total_chars >= 0.8 if total_chars > 0 else False

def should_fetch_next_page(data, search_word, has_exact_match):
    """判断是否需要获取下一页数据"""
    # 如果第一页已经有精确匹配的结果，则不翻页
    if has_exact_match:
        print(f"DEBUG: Exact match found. No need for next page.", file=sys.stderr)
        return False
        
    if len(data) < 20:  # 第一页结果不足20个，说明没有下一页
        return False
    
    # 统计高优先级条目（只有reading，没有word的片假名条目）
    high_priority_count = 0
    for entry in data:
        if entry.get('japanese'):
            japanese_entry = entry['japanese'][0]
            if japanese_entry.get('reading') and not japanese_entry.get('word'):
                # 检查是否是片假名
                reading = japanese_entry.get('reading', '')
                if is_katakana_reading(reading):
                    high_priority_count += 1
    
    print(f"DEBUG: Found {high_priority_count} high-priority katakana entries in first page", file=sys.stderr)
    # 如果高优先级条目少于5个，需要翻页
    return high_priority_count < 5

def jisho_search_with_pagination(word, page=1):
    """使用 Jisho API 搜索单词，支持分页"""
    cache_key = hashlib.md5(f"{word}_page_{page}".encode('utf-8')).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")

    # 检查缓存，永不过期
    if os.path.exists(cache_file):
        print(f"DEBUG: Loading from cache for '{word}' page {page}", file=sys.stderr)
        with open(cache_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    try:
        url = f"https://jisho.org/api/v1/search/words?keyword={urllib.parse.quote(word)}&page={page}"
        
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )
        
        print(f"DEBUG: Fetching from Jisho API for '{word}' page {page}", file=sys.stderr)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            result = json.loads(data)
            
            if result and result.get('data'):
                # 保存到缓存
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(result['data'], f, ensure_ascii=False, indent=2)
                return result['data']
                
        return None
        
    except Exception as e:
        print(f"Jisho API 错误 (page {page}): {str(e)}", file=sys.stderr)
        return None

def main(query):
    """主函数"""
    start_total_time = time.time()
    
    data = jisho_search(query)
    
    if not data:
        print(json.dumps({"items": [{"title": "Not Found", "subtitle": "No results for '{}'".format(query)}]}))
        return

    # 检查第一页是否有精确匹配（音译词汇）
    has_exact_match = False
    for entry in data:
        if not entry.get('japanese') or not entry.get('senses'):
            continue
        
        japanese_entry = entry['japanese'][0]
        reading = japanese_entry.get('reading', '')
        
        if is_katakana_reading(reading) and not japanese_entry.get('word'):
            english_definitions = entry['senses'][0].get('english_definitions', [])
            
            # 检查是否是直接音译词汇的标准：
            # 1. 有且仅有一个定义且完全匹配查询词
            # 2. 或者是较长的片假名（4+字符）且定义中有完全匹配项
            for definition in english_definitions:
                if query.lower() == definition.lower():
                    # 严格标准：只有单一定义的情况才认为是音译词
                    if len(english_definitions) == 1:
                        has_exact_match = True
                        print(f"DEBUG: Found transliteration match: {reading} = {definition}", file=sys.stderr)
                        break
                    # 或者是长片假名词汇（更可能是音译）
                    elif len(reading) >= 4:
                        has_exact_match = True
                        print(f"DEBUG: Found long katakana match: {reading} = {definition}", file=sys.stderr)
                        break
                    else:
                        print(f"DEBUG: Found semantic match, not transliteration: {reading} = {definition} ({len(english_definitions)} definitions)", file=sys.stderr)
        if has_exact_match:
            break
            
    # 根据情况决定是否获取下一页
    if should_fetch_next_page(data, query, has_exact_match):
        print(f"DEBUG: Fetching next page for '{query}'", file=sys.stderr)
        next_page_data = jisho_search_with_pagination(query, page=2)
        if next_page_data:
            data.extend(next_page_data)

    items = []
    seen_readings = set()
    
    # 增加排序逻辑：精确匹配的条目优先
    sorted_data = sorted(data, key=lambda entry: (
        not (
            is_katakana_reading(entry.get('japanese', [{}])[0].get('reading', '')) and
            not entry.get('japanese', [{}])[0].get('word') and
            any(
                query.lower() == definition.lower() or definition.lower().startswith(query.lower())
                for definition in entry.get('senses', [{}])[0].get('english_definitions', [])
            )
        ),
        # 其他排序条件可以加在这里
    ))

    for entry in sorted_data:
        if not entry.get('japanese'):
            continue
            
        japanese_entry = entry['japanese'][0]
        reading = japanese_entry.get('reading', '')
        
        # 仅处理纯片假名读音且无汉字写法的条目
        if is_katakana_reading(reading) and not japanese_entry.get('word'):
            if reading not in seen_readings:
                subtitle = ""
                if entry.get('senses'):
                    senses = entry['senses'][0]
                    parts_of_speech = ", ".join(senses.get('parts_of_speech', []))
                    english_definitions = "; ".join(senses.get('english_definitions', []))
                    
                    subtitle_parts = []
                    if parts_of_speech:
                        subtitle_parts.append(f"[{parts_of_speech}]")
                    if english_definitions:
                        subtitle_parts.append(english_definitions)
                    subtitle = " ".join(subtitle_parts)

                items.append({
                    "title": reading,
                    "subtitle": subtitle,
                    "arg": reading,
                    "text": {
                        "copy": reading,
                        "largetype": reading
                    }
                })
                seen_readings.add(reading)

    if not items:
        items.append({"title": "No Katakana Found", "subtitle": "Could not find a Katakana reading for '{}'".format(query)})

    print(json.dumps({"items": items}))
    
    end_total_time = time.time()
    print(f"DEBUG: Total execution time: {end_total_time - start_total_time:.3f} seconds", file=sys.stderr)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        print(json.dumps({"items": [{"title": "请输入英文单词进行查询"}]}))
