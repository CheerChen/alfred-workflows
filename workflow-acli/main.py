# -*- coding: utf-8 -*-
import sys
import json
import subprocess
import os
import time
import hashlib

# --- 配置 ---
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_BASE_URL = os.getenv('JIRA_BASE_URL')
DEFAULT_JQL_PROJECT = f"project = {os.getenv('JIRA_PROJECT', 'DBRE')}"
jira_type_value = os.getenv('JIRA_TYPE', 'タスク')
DEFAULT_JQL_TYPE = f'Type = "{jira_type_value}"' if jira_type_value else ""
CACHE_EXPIRY = 3600
CACHE_DIR = os.getenv('alfred_workflow_data', os.path.expanduser('~/.alfred_workflow_data_jira'))
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def _execute_acli_command_actual(jql_query, paginate=False):
    """实际执行 acli 命令的内部函数，并包含调试日志"""
    try:
        command = [
            'acli', 'jira', 'workitem', 'search',
            '--jql', jql_query,
            '--json'
        ]
        command.extend(['--fields', 'key,summary,status'])
        if paginate:
            command.append('--paginate')
        else:
            command.extend(['--limit', '50'])
            
        # --- VVVV  新增的调试日志 VVVV ---
        # 1. 打印将要执行的命令到 stderr
        # 为了方便阅读和复制，我们将命令列表格式化为字符串
        printable_command = ' '.join(f"'{part}'" if ' ' in part else part for part in command)
        print(f"DEBUG: Executing command -> {printable_command}", file=sys.stderr)

        # 2. 记录开始时间
        start_time = time.monotonic()
        # --- ^^^^  新增结束 ^^^^ ---

        result = subprocess.check_output(command, text=True, stderr=subprocess.PIPE)

        # --- VVVV  新增的调试日志 VVVV ---
        # 3. 记录结束时间并打印耗时
        end_time = time.monotonic()
        duration = end_time - start_time
        print(f"DEBUG: Command finished in {duration:.3f} seconds.", file=sys.stderr)
        # --- ^^^^  新增结束 ^^^^ ---
        
        return json.loads(result)
    except FileNotFoundError:
        print("DEBUG: Error -> acli command not found.", file=sys.stderr)
        return {"error": "ACLI not found", "message": "Atlassian CLI (acli) is not in your PATH."}
    except subprocess.CalledProcessError as e:
        print(f"DEBUG: Error -> acli command failed with stderr: {e.stderr.strip()}", file=sys.stderr)
        return {"error": "ACLI command failed", "message": e.stderr.strip()}
    except json.JSONDecodeError:
        print("DEBUG: Error -> Failed to decode JSON from acli.", file=sys.stderr)
        return {"error": "JSON Decode Error", "message": "Failed to parse acli output."}

def execute_acli_command(jql_query, paginate=False):
    """带缓存的 acli 命令执行器"""
    cache_key_str = f"{jql_query}_{paginate}"
    cache_key = hashlib.md5(cache_key_str.encode('utf-8')).hexdigest()
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")

    if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file)) < CACHE_EXPIRY:
        # --- VVVV  新增的调试日志 VVVV ---
        print("DEBUG: Loading from CACHE.", file=sys.stderr)
        # --- ^^^^  新增结束 ^^^^ ---
        with open(cache_file, 'r') as f:
            return json.load(f)
            
    # 如果缓存无效，则执行真实命令，该函数内部已包含日志
    data = _execute_acli_command_actual(jql_query, paginate)
    
    if "error" not in data:
        with open(cache_file, 'w') as f:
            json.dump(data, f)
            
    return data

# ... main() 和其他函数保持不变 ...
def generate_alfred_item(title, subtitle, arg, uid):
    return {"uid": uid, "title": title, "subtitle": subtitle, "arg": arg, "valid": True}

def main():
    if not JIRA_USERNAME or not JIRA_BASE_URL:
        error_item = generate_alfred_item(title="Workflow Configuration Error", subtitle="Please set JIRA_USERNAME and JIRA_BASE_URL in workflow variables [x]", arg="", uid="config-error")
        print(json.dumps({"items": [error_item]}))
        return

    query_str = sys.argv[1] if len(sys.argv) > 1 else ""
    query_parts = query_str.split()
    
    should_paginate_all = False
    if '--all' in query_parts:
        should_paginate_all = True
        query_parts.remove('--all')

    jql_clauses = [DEFAULT_JQL_PROJECT]
    if DEFAULT_JQL_TYPE:
        jql_clauses.append(DEFAULT_JQL_TYPE)
        
    search_terms = []
    if query_parts and query_parts[0].lower() == 'me':
        jql_clauses.append(f"Assignee = '{JIRA_USERNAME}'")
        search_terms = query_parts[1:]
    else:
        search_terms = query_parts

    if search_terms:
        full_search_str = " ".join(search_terms)
        jql_clauses.append(f'text ~ "{full_search_str}*"')

    jql_core = " AND ".join(jql_clauses)
    final_jql = f"{jql_core} ORDER BY key DESC"

    search_results = execute_acli_command(final_jql, paginate=should_paginate_all)
    alfred_items = []

    if isinstance(search_results, dict) and "error" in search_results:
        alfred_items.append(generate_alfred_item(title=f"Error: {search_results['error']}", subtitle=search_results['message'], arg="", uid="error"))
    elif not search_results:
        alfred_items.append(generate_alfred_item(title="No Results Found", subtitle="Try adding --all to your search to load all pages.", arg="", uid="no-results"))
    else:
        count = len(search_results)
        subtitle_prefix = f"Loaded {count} issues."
        if not should_paginate_all and count >= 50:
            subtitle_prefix += " (use --all to load more)"

        for issue in search_results:
            issue_key = issue.get("key", "N/A")
            fields = issue.get("fields", {})
            summary = fields.get("summary", "No Summary")
            status_obj = fields.get("status", {})
            status = status_obj.get("name", "No Status") if status_obj else "No Status"
            
            alfred_items.append(generate_alfred_item(
                title=summary,
                subtitle=f"{subtitle_prefix} | {issue_key} | {status}",
                arg=f"{JIRA_BASE_URL}/browse/{issue_key}",
                uid=issue_key
            ))
            
    print(json.dumps({"items": alfred_items}))

if __name__ == "__main__":
    main()