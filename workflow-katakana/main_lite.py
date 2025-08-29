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

def google_translate(text, src_lang='en', dest_lang='ja'):
    """使用Google翻译API进行翻译"""
    try:
        # Google Translate API endpoint (与原脚本相同)
        api_url = 'https://translate.googleapis.com/translate_a/single'
        
        params = {
            'client': 'gtx',
            'dt': 't',
            'sl': src_lang,
            'tl': dest_lang,
            'q': text.strip()
        }
        
        url = api_url + build_query_string(params)
        
        # Create request with user agent to avoid blocking
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
        )
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = response.read().decode('utf-8')
            
        # Parse response (similar to original script)
        # Replace single quotes that might break JSON parsing
        data = data.replace("'", '\u2019')
        result = json.loads(data)
        
        if result and result[0]:
            # Extract translated text
            translated_parts = []
            for item in result[0]:
                if item[0]:
                    translated_parts.append(item[0])
            
            return ''.join(translated_parts).strip()
        
        return None
        
    except (URLError, json.JSONDecodeError, IndexError) as e:
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
    
    # Direct translation to Japanese (which should include katakana)
    translated = google_translate(query, 'en', 'ja')
    
    if translated and not translated.startswith("翻译错误"):
        # Extract katakana from the translation
        katakana_list = extract_katakana(translated)
        
        if katakana_list:
            # Main result with all katakana
            all_katakana = ''.join(katakana_list)
            items.append({
                "title": all_katakana,
                "subtitle": f"'{query}' 的片假名形式",
                "arg": all_katakana,
                "icon": {"type": "default"}
            })
            
            # If multiple katakana words, show them separately
            if len(katakana_list) > 1:
                for i, katakana in enumerate(katakana_list):
                    items.append({
                        "title": katakana,
                        "subtitle": f"片假名部分 {i+1}",
                        "arg": katakana,
                        "icon": {"type": "default"}
                    })
        
        # Also show the full Japanese translation
        items.append({
            "title": translated,
            "subtitle": "完整的日文翻译",
            "arg": translated,
            "icon": {"type": "default"}
        })
        
    else:
        # Error or no translation
        error_msg = translated if translated else "无法获取翻译结果"
        items.append({
            "title": "翻译失败",
            "subtitle": error_msg,
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