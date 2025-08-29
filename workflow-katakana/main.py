#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import urllib.request
import urllib.parse
from urllib.error import URLError
import re

def build_query_string(params):
    """构建查询字符串"""
    return '?' + urllib.parse.urlencode(params)

def google_translate_phonetic(text, src_lang='en', dest_lang='ja'):
    """使用Google翻译API进行音译翻译"""
    try:
        # Google Translate API endpoint
        api_url = 'https://translate.googleapis.com/translate_a/single'
        
        # 尝试多种方法获取音译结果
        methods = [
            # 方法1: 直接翻译，但在单词前后加特殊标记引导音译
            f"phonetic transcription of {text}",
            # 方法3: 直接翻译（保留原方法作为备选）
            text
        ]
        
        for method_text in methods:
            params = {
                'client': 'gtx',
                'dt': 't',
                'sl': src_lang,
                'tl': dest_lang,
                'q': method_text.strip()
            }
            
            url = api_url + build_query_string(params)
            
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                }
            )
            
            try:
                with urllib.request.urlopen(req, timeout=10) as response:
                    data = response.read().decode('utf-8')
                    
                data = data.replace("'", '\u2019')
                result = json.loads(data)
                
                if result and result[0]:
                    translated_parts = []
                    for item in result[0]:
                        if item[0]:
                            translated_parts.append(item[0])
                    
                    translated_text = ''.join(translated_parts).strip()
                    
                    # 提取片假名
                    katakana_matches = extract_katakana(translated_text)
                    
                    # 如果找到片假名且长度合理，返回结果
                    if katakana_matches and any(len(k) >= 2 for k in katakana_matches):
                        return translated_text
                        
            except:
                continue
        
        return "无法转换"
        
    except Exception as e:
        return f"翻译错误: {str(e)}"

def extract_katakana(text):
    """提取文本中的片假名"""
    # Katakana regex pattern (与原脚本相同的正则表达式)
    katakana_pattern = r'[\u30A1-\u30FA\u30FD-\u30FF][\u3099\u309A\u30A1-\u30FF]*[\u3099\u309A\u30A1-\u30FA\u30FC-\u30FF]|[\uFF66-\uFF6F\uFF71-\uFF9D][\uFF65-\uFF9F]*[\uFF66-\uFF9F]'
    katakana_matches = re.findall(katakana_pattern, text)
    return katakana_matches

def create_alfred_items(query):
    """创建Alfred结果项"""
    items = []
    
    if not query:
        items.append({
            "title": "英文转片假名",
            "subtitle": "输入英文单词或短语来转换为片假名",
            "icon": {"type": "default"}
        })
        return items
    
    # 方法1: 尝试音译翻译
    translated = google_translate_phonetic(query, 'en', 'ja')
    
    if translated and not translated.startswith("翻译错误") and not translated.startswith("无法转换"):
        katakana_list = extract_katakana(translated)
        
        if katakana_list:
            # 主要结果：所有片假名
            all_katakana = ''.join(katakana_list)
            items.append({
                "title": all_katakana,
                "subtitle": f"'{query}' 的片假名音译",
                "arg": all_katakana,
                "icon": {"type": "default"}
            })
            
            # 如果有多个片假名词，分别显示
            if len(katakana_list) > 1:
                for i, katakana in enumerate(katakana_list):
                    items.append({
                        "title": katakana,
                        "subtitle": f"片假名部分 {i+1}",
                        "arg": katakana,
                        "icon": {"type": "default"}
                    })
    
    # 如果没有任何结果
    if not items:
        items.append({
            "title": "无法转换",
            "subtitle": f"无法将 '{query}' 转换为片假名，请尝试其他单词",
            "icon": {"type": "error"}
        })
    
    return items

def main():
    # Get query from Alfred
    query = sys.argv[1] if len(sys.argv) > 1 else ""
    
    # Create Alfred Script Filter JSON output
    result = {
        "items": create_alfred_items(query)
    }
    
    # Output JSON for Alfred
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()