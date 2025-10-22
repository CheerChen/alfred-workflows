# -*- coding: utf-8 -*-
import sys
import json
import subprocess
import os
import time
import urllib.parse

# --- ++ 新增配置：可用的服务和Profile ++ ---
# 在这里定义你的服务和Profile，以便脚本提供提示
AVAILABLE_SERVICES = {
    "ec2": " Elastic Compute Cloud (EC2) instances",
    "rds": " Relational Database Service (RDS) instances",
    "lambda": " Lambda functions",
    "dynamo": " DynamoDB tables",
    "sfn": " Step Functions",
    "secret": " Secrets Manager",
    "role": " IAM Roles",
    "s3": " S3 buckets",
    "sqs": " SQS queues"
}

AVAILABLE_PROFILES = {
	"lab": " Lab environment",
    "inte": " Integration environment",
    "prod": " Production environment",
    "dev": " Development environment",
    "stg": " Staging environment"
}
# -------------------------------------------

# --- 配置 ---
DEFAULT_REGION = "ap-northeast-1"
CACHE_EXPIRY = 3600
# ----------------

query_str = sys.argv[1]

CACHE_DIR = os.getenv('alfred_workflow_data', os.path.expanduser('~/.alfred_workflow_data'))
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# --- 函数部分 (与之前版本相同，无需关注) ---
def get_region_for_profile(profile):
    try:
        region = subprocess.check_output(['aws', 'configure', 'get', 'region', '--profile', profile], text=True).strip()
        return region
    except subprocess.CalledProcessError:
        return DEFAULT_REGION

def execute_aws_command(command, cache_key):
    cache_file = os.path.join(CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file) and (time.time() - os.path.getmtime(cache_file)) < CACHE_EXPIRY:
        with open(cache_file, 'r') as f: return json.load(f)
    try:
        result = subprocess.check_output(command, text=True, stderr=subprocess.PIPE)
        data = json.loads(result)
        with open(cache_file, 'w') as f: json.dump(data, f)
        return data
    except subprocess.CalledProcessError as e:
        # --- VVVV  这是核心修改：捕获并识别 Token 过期错误 VVVV ---
        error_output = e.stderr.strip()
        # 检测多种 AWS SSO Token 过期的错误模式
        token_expired_patterns = [
            "Expired",
            "expired",
            "Token for",
            "does not exist",
            "Error loading SSO Token",
            "SSO session",
            "No credentials"
        ]
        
        if any(pattern in error_output for pattern in token_expired_patterns):
            # 返回一个特殊的错误类型，以便 main 函数识别
            return {"error": "ExpiredToken", "message": error_output}
        else:
            # 对于其他错误，仍然可以返回一个通用错误
            return {"error": "AWSError", "message": error_output}
        # --- ^^^^  修改结束 ^^^^ ---
    except json.JSONDecodeError: 
        return None

def generate_alfred_item(title, subtitle, arg, uid, mods=None, valid=True, autocomplete=None):
    """
    生成一个 Alfred item。
    新增 mods 参数，用于处理修饰键（Cmd, Alt, etc.）。
    """
    item = {
        "uid": uid,
        "title": title,
        "subtitle": subtitle,
        "arg": arg,
        "valid": valid
    }
    if autocomplete:
        item["autocomplete"] = autocomplete
    # --- VVVV 新增逻辑 VVVV ---
    if mods:
        item["mods"] = mods
    # --- ^^^^ 新增逻辑结束 ^^^^ ---
    return item

def handle_aws_response(data, profile=None):
    """
    统一处理 AWS 响应，检查错误并返回相应的 Alfred items
    返回: (is_error: bool, alfred_items: list)
    """
    if isinstance(data, dict) and "error" in data:
        if data["error"] == "ExpiredToken":
            # 如果有 profile，则生成带 profile 的命令
            if profile:
                sso_command = f"aws sso login --profile {profile}"
                subtitle = f"Press Enter to run 'aws sso login --profile {profile}'"
            else:
                sso_command = "aws sso login"
                subtitle = "Press Enter to run 'aws sso login'"
                
            error_item = generate_alfred_item(
                title="AWS Session Expired",
                subtitle=subtitle,
                arg=sso_command,
                uid="aws-sso-login",
                valid=True
            )
        else:
            error_item = generate_alfred_item(
                title="❌ AWS CLI Error", 
                subtitle=data.get("message", "Unknown error"), 
                arg="error",
                uid="aws-error",
                valid=False
            )
        return True, [error_item]
    return False, []

def get_tag_name(tags):
    if not tags: return ""
    for tag in tags:
        if tag.get('Key') == 'Name': return tag.get('Value', '')
    return ""

def search_aws_resources(service, profile, region, search_str):
    """
    通用的AWS资源搜索函数，减少代码重复
    """
    # 定义每个服务的配置
    service_configs = {
        'ec2': {
            'command': ['aws', 'ec2', 'describe-instances', '--profile', profile, '--region', region, '--query', 'Reservations[].Instances[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/ec2/v2/home?region={region}#InstanceDetails:instanceId={{id}}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('InstanceId', 'N/A'),
                'name': get_tag_name(item.get('Tags', [])),
                'extra_info': f"State: {item.get('State', {}).get('Name', 'N/A')}"
            }
        },
        'rds': {
            'command': ['aws', 'rds', 'describe-db-instances', '--profile', profile, '--region', region, '--query', 'DBInstances[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/rds/home?region={region}#database:id={{id}};is-cluster=false",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('DBInstanceIdentifier'),
                'name': item.get('DBInstanceIdentifier'),
                'extra_info': f"Status: {item.get('DBInstanceStatus')} | Engine: {item.get('Engine')}"
            }
        },
        'lambda': {
            'command': ['aws', 'lambda', 'list-functions', '--profile', profile, '--region', region, '--query', 'Functions[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/lambda/home?region={region}#/functions/{{id}}?tab=code",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('FunctionName'),
                'name': item.get('FunctionName'),
                'extra_info': f"Runtime: {item.get('Runtime')}"
            }
        },
        'dynamo': {
            'command': ['aws', 'dynamodb', 'list-tables', '--profile', profile, '--region', region, '--query', 'TableNames[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/dynamodbv2/home?region={region}#table?name={{id}}&tab=overview",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item,
                'name': item,
                'extra_info': f"Table Name: {item}"
            }
        },
        'sfn': {
            'command': ['aws', 'stepfunctions', 'list-state-machines', '--profile', profile, '--region', region, '--query', 'stateMachines[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/states/home?region={region}#/statemachines/view/{{id}}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('stateMachineArn'),
                'name': item.get('name'),
                'extra_info': f"ARN: {item.get('stateMachineArn')}"
            }
        },
        'secret': {
            'command': ['aws', 'secretsmanager', 'list-secrets', '--profile', profile, '--region', region, '--query', 'SecretList[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/secretsmanager/secret?name={{id}}&region={region}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('Name'),
                'name': item.get('Name'),
                'extra_info': f"Secret Name: {item.get('Name')}"
            }
        },
        'role': {
            'command': ['aws', 'iam', 'list-roles', '--profile', profile, '--query', 'Roles[]'],
            'url_template': f"https://console.aws.amazon.com/iam/home#/roles/{{id}}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('RoleName'),
                'name': item.get('RoleName'),
                'extra_info': f"Path: {item.get('Path', '/')} | Created: {item.get('CreateDate', 'N/A')[:10] if item.get('CreateDate') else 'N/A'}"
            }
        },
        's3': {
            'command': ['aws', 's3api', 'list-buckets', '--profile', profile, '--query', 'Buckets[]'],
            'url_template': f"https://s3.console.aws.amazon.com/s3/buckets/{{id}}?region={region}&tab=objects",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('Name'),
                'name': item.get('Name'),
                'extra_info': f"Created: {item.get('CreationDate', '')[:10] if item.get('CreationDate') else 'N/A'}"
            }
        },
        'sqs': {
            'command': ['aws', 'sqs', 'list-queues', '--profile', profile, '--region', region, '--query', 'QueueUrls[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/sqs/v2/home?region={region}#/queues/{{encoded_id}}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item,
                'name': item.split('/')[-1] if item else 'N/A',
                'extra_info': f"Queue URL: {item}",
                'encoded_id': urllib.parse.quote(item, safe='') if item else ''
            }
        }
    }
    
    if service not in service_configs:
        return [generate_alfred_item(f"Service '{service}' not supported", "", service, service, False)]
    
    config = service_configs[service]
    
    # 执行AWS命令
    cache_key_region = region or "global"
    data = execute_aws_command(config['command'], f"{service}_{profile}_{cache_key_region}")
    
    # 使用统一的错误处理
    is_error, error_items = handle_aws_response(data, profile)
    if is_error:
        return error_items
    
    # 提取资源列表
    items = config['extract_items'](data)
    if not items:
        return []
    
    results = []
    for item in items:
        item_data = config['get_item_data'](item)
        
        # 过滤搜索结果
        if search_str:
            search_lower = search_str.lower()
            if not (search_lower in (item_data['name'] or '').lower() or 
                   search_lower in (item_data['id'] or '').lower()):
                continue
        
        # 生成控制台URL
        destination_url = config['url_template'].format(
            id=item_data.get('id', ''),
            region=region,
            encoded_id=item_data.get('encoded_id', ''),
            name=item_data.get('name', ''),
            source_type=item_data.get('source_type', 'instance')
        )
        open_arg_template = config.get('open_arg_template')
        if open_arg_template:
            open_arg = open_arg_template.format(
                id=item_data.get('id', ''),
                region=region,
                encoded_id=item_data.get('encoded_id', ''),
                name=item_data.get('name', ''),
                source_type=item_data.get('source_type', 'instance')
            )
        else:
            open_arg = config.get('open_arg', destination_url)
        
        # 创建修饰键配置 - Cmd+Enter 复制URL到剪贴板
        mods = {
            "cmd": {
                "valid": True,
                "arg": destination_url,
                "subtitle": "⌘ Hold Cmd+Enter to copy URL to clipboard"
            }
        }
        
        # 生成Alfred项目
        results.append(generate_alfred_item(
            title=f"{service.upper()}: {item_data['name'] or item_data['id']}",
            subtitle=f"{item_data['extra_info']} | Press Enter to open",
            arg=open_arg,
            uid=item_data.get('id') or item_data.get('name') or destination_url,
            mods=mods
        ))
    
    return results

# 为了向后兼容，保留原有的函数名
def search_ec2(profile, region, search_str):
    return search_aws_resources('ec2', profile, region, search_str)

def search_rds(profile, region, search_str):
    return search_aws_resources('rds', profile, region, search_str)

def search_lambda(profile, region, search_str):
    return search_aws_resources('lambda', profile, region, search_str)

def search_dynamodb(profile, region, search_str):
    return search_aws_resources('dynamo', profile, region, search_str)

def search_sfn(profile, region, search_str):
    return search_aws_resources('sfn', profile, region, search_str)

def search_secret(profile, region, search_str):
    return search_aws_resources('secret', profile, region, search_str)

def search_role(profile, region, search_str):
    return search_aws_resources('role', profile, region, search_str)

def search_s3(profile, region, search_str):
    return search_aws_resources('s3', profile, region, search_str)

def search_sqs(profile, region, search_str):
    return search_aws_resources('sqs', profile, region, search_str)
# --------------------------------------------------------

# --- ++ 主逻辑 (大幅增强) ++ ---
def main():
    query_parts = query_str.split()
    num_parts = len(query_parts)
    alfred_items = []

    # --- 阶段1：用户刚输入 aws，提示选择 Service ---
    if num_parts == 0 or (num_parts == 1 and not query_str.endswith(' ')):
        search = query_parts[0] if num_parts == 1 else ""
        for service, desc in AVAILABLE_SERVICES.items():
            if search.lower() in service.lower():
                alfred_items.append(generate_alfred_item(
                    title=f"Service: {service}",
                    subtitle=f"Search for {desc}",
                    arg=service,
                    uid=service,
                    valid=False,
                    autocomplete=f"{service} "
                ))
    
    # --- 阶段2：用户已选择 Service，提示选择 Profile ---
    elif num_parts == 1 and query_str.endswith(' '):
        service = query_parts[0]
        if service not in AVAILABLE_SERVICES:
            alfred_items.append(generate_alfred_item("Invalid Service", f"'{service}' is not supported", service, service, False))
        else:
            for profile, desc in AVAILABLE_PROFILES.items():
                alfred_items.append(generate_alfred_item(
                    title=f"Profile: {profile}",
                    subtitle=f"Use the {desc}",
                    arg=f"{service} {profile}",
                    uid=profile,
                    valid=False,
                    autocomplete=f"{service} {profile} "
                ))

    # --- 阶段3：用户已选择 Service 和 Profile，执行真正的搜索 ---
    elif num_parts >= 2:
        service, profile = query_parts[0], query_parts[1]
        search_str = " ".join(query_parts[2:])

        if service not in AVAILABLE_SERVICES or profile not in AVAILABLE_PROFILES:
             alfred_items.append(generate_alfred_item("Invalid Input", "Please select a valid service and profile", query_str, query_str, False))
        else:
            region = get_region_for_profile(profile)
            service_map = {
                'ec2': search_ec2, 
                'rds': search_rds, 
                'lambda': search_lambda, 
                'sfn': search_sfn, 
                'dynamo': search_dynamodb, 
                'secret': search_secret,
                'role': search_role,
                's3': search_s3,
                'sqs': search_sqs
                }
            
            search_function = service_map.get(service)
            if search_function:
                alfred_items = search_function(profile, region, search_str)
            else:
                alfred_items.append(generate_alfred_item(f"Service '{service}' search not implemented yet", "", service, service, False))
    
    # 如果最终没有结果，显示提示
    if not alfred_items:
        alfred_items.append(generate_alfred_item("No Results", "No items match your query", query_str, query_str, False))

    print(json.dumps({"items": alfred_items}))

if __name__ == "__main__":
    main()
