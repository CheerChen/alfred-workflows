# -*- coding: utf-8 -*-
import sys
import json
import subprocess
import os
import time
import urllib.parse
import configparser

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
    "sqs": " SQS queues",
    "his": " History of accessed resources"
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

try:
    query_str = sys.argv[1]
except IndexError:
    query_str = ""

CACHE_DIR = os.getenv('alfred_workflow_data', os.path.expanduser('~/.alfred_workflow_data'))
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# --- 函数部分 ---
def get_sso_start_url(profile):
    """
    Parses ~/.aws/config to find the sso_start_url for a given profile.
    """
    config = configparser.ConfigParser()
    config_path = os.path.expanduser('~/.aws/config')
    if not os.path.exists(config_path):
        return None
    
    config.read(config_path)
    
    profile_section_name = f"profile {profile}"
    
    if config.has_section(profile_section_name):
        profile_section = config[profile_section_name]
        
        if profile_section.get('sso_start_url'):
            return profile_section.get('sso_start_url')
            
        if profile_section.get('sso_session'):
            sso_session_name = profile_section.get('sso_session')
            sso_session_section_name = f"sso-session {sso_session_name}"
            
            if config.has_section(sso_session_section_name):
                sso_session_section = config[sso_session_section_name]
                return sso_session_section.get('sso_start_url')
                
    return None

def get_region_for_profile(profile):
    try:
        region = subprocess.check_output(['aws', 'configure', 'get', 'region', '--profile', profile], text=True).strip()
        return region
    except subprocess.CalledProcessError:
        return DEFAULT_REGION

def check_aws_credentials(profile):
    """
    快速检查 AWS 凭证是否有效
    使用 aws sts get-caller-identity 命令进行轻量级验证
    """
    try:
        result = subprocess.run(
            ['aws', 'sts', 'get-caller-identity', '--profile', profile], 
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False
    except Exception:
        return False

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
        error_output = e.stderr.strip()
        token_expired_patterns = [
            "Expired", "expired", "Token for", "does not exist",
            "Error loading SSO Token", "SSO session", "No credentials"
        ]
        
        if any(pattern in error_output for pattern in token_expired_patterns):
            return {"error": "ExpiredToken", "message": error_output}
        else:
            return {"error": "AWSError", "message": error_output}
    except json.JSONDecodeError: 
        return None

def generate_alfred_item(title, subtitle, arg, uid, mods=None, valid=True, autocomplete=None):
    item = {
        "uid": uid, "title": title, "subtitle": subtitle,
        "arg": arg, "valid": valid
    }
    if autocomplete:
        item["autocomplete"] = autocomplete
    if mods:
        item["mods"] = mods
    return item

def generate_status_item(status_type, service=None, profile=None, message=None):
    """
    生成状态指示项
    """
    if status_type == "loading":
        return generate_alfred_item(
            title=f"🔄 Loading {service.upper()} resources from {profile}...",
            subtitle="Fetching data from AWS API, please wait...",
            arg="loading",
            uid="loading-status",
            valid=False
        )
    elif status_type == "credentials_invalid":
        sso_command = f"aws sso login --profile {profile}"
        return generate_alfred_item(
            title="🔐 AWS Credentials Invalid",
            subtitle=f"Press Enter to run: {sso_command}",
            arg=sso_command,
            uid="credentials-invalid",
            valid=True
        )
    elif status_type == "credentials_checking":
        return generate_alfred_item(
            title=f"🔍 Checking credentials for {profile}...",
            subtitle="Validating AWS access, please wait...",
            arg="checking",
            uid="credentials-checking",
            valid=False
        )
    elif status_type == "profile_not_found":
        available_profiles = ", ".join(AVAILABLE_PROFILES.keys())
        return generate_alfred_item(
            title="❌ Profile Not Found",
            subtitle=f"'{profile}' not configured. Available: {available_profiles}",
            arg="profile-error",
            uid="profile-not-found",
            valid=False
        )
    elif status_type == "service_not_supported":
        return generate_alfred_item(
            title="❌ Service Not Supported",
            subtitle=f"'{service}' is not supported by this workflow",
            arg="service-error",
            uid="service-not-supported",
            valid=False
        )
    elif status_type == "connected_ready":
        return generate_alfred_item(
            title=f"✅ Connected to {profile}",
            subtitle=f"AWS credentials valid. Searching {service.upper()} resources...",
            arg="connected",
            uid="connected-status",
            valid=False
        )
    elif status_type == "custom_error":
        return generate_alfred_item(
            title="❌ Error",
            subtitle=message or "An error occurred",
            arg="error",
            uid="custom-error",
            valid=False
        )
    else:
        return generate_alfred_item(
            title="Unknown Status",
            subtitle="Unknown status type",
            arg="unknown",
            uid="unknown-status",
            valid=False
        )

def handle_aws_response(data, profile=None):
    if not (isinstance(data, dict) and "error" in data):
        return False, []

    if data["error"] == "ExpiredToken":
        sso_command = "aws sso login"
        if profile:
            sso_command += f" --profile {profile}"

        start_url = get_sso_start_url(profile) if profile else None

        if start_url:
            action_command = f"{sso_command} && open '{start_url}'"
            item = generate_alfred_item(
                title="AWS Session Expired",
                subtitle="Press Enter to log in and open AWS Console.",
                arg=action_command,
                uid="aws-sso-login-and-open",
                valid=True
            )
        else:
            item = generate_alfred_item(
                title="AWS Session Expired",
                subtitle=f"Press Enter to run '{sso_command}'",
                arg=sso_command,
                uid="aws-sso-login",
                valid=True
            )
        return True, [item]
    else:
        item = generate_alfred_item(
            title="❌ AWS CLI Error",
            subtitle=data.get("message", "Unknown error"),
            arg="error",
            uid="aws-error",
            valid=False
        )
        return True, [item]

def get_tag_name(tags):
    if not tags: return ""
    for tag in tags:
        if tag.get('Key') == 'Name': return tag.get('Value', '')
    return ""

def search_aws_resources(service, profile, region, search_str):
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
            'get_item_data': lambda item: { 'id': item, 'name': item, 'extra_info': f"Table Name: {item}" }
        },
        'sfn': {
            'command': ['aws', 'stepfunctions', 'list-state-machines', '--profile', profile, '--region', region, '--query', 'stateMachines[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/states/home?region={region}#/statemachines/view/{{id}}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('stateMachineArn'), 'name': item.get('name'),
                'extra_info': f"ARN: {item.get('stateMachineArn')}"
            }
        },
        'secret': {
            'command': ['aws', 'secretsmanager', 'list-secrets', '--profile', profile, '--region', region, '--query', 'SecretList[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/secretsmanager/secret?name={{id}}&region={region}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: { 'id': item.get('Name'), 'name': item.get('Name'), 'extra_info': f"Secret Name: {item.get('Name')}" }
        },
        'role': {
            'command': ['aws', 'iam', 'list-roles', '--profile', profile, '--query', 'Roles[]'],
            'url_template': f"https://console.aws.amazon.com/iam/home#/roles/{{id}}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('RoleName'), 'name': item.get('RoleName'),
                'extra_info': f"Path: {item.get('Path', '/')} | Created: {item.get('CreateDate', 'N/A')[:10] if item.get('CreateDate') else 'N/A'}"
            }
        },
        's3': {
            'command': ['aws', 's3api', 'list-buckets', '--profile', profile, '--query', 'Buckets[]'],
            'url_template': f"https://s3.console.aws.amazon.com/s3/buckets/{{id}}?region={region}&tab=objects",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item.get('Name'), 'name': item.get('Name'),
                'extra_info': f"Created: {item.get('CreationDate', '')[:10] if item.get('CreationDate') else 'N/A'}"
            }
        },
        'sqs': {
            'command': ['aws', 'sqs', 'list-queues', '--profile', profile, '--region', region, '--query', 'QueueUrls[]'],
            'url_template': f"https://{region}.console.aws.amazon.com/sqs/v2/home?region={region}#/queues/{{encoded_id}}",
            'extract_items': lambda data: data if data else [],
            'get_item_data': lambda item: {
                'id': item, 'name': item.split('/')[-1] if item else 'N/A',
                'extra_info': f"Queue URL: {item}",
                'encoded_id': urllib.parse.quote(item, safe='') if item else ''
            }
        }
    }
    
    if service not in service_configs:
        return [generate_alfred_item(f"Service '{service}' not supported", "", service, service, False)]
    
    config = service_configs[service]
    cache_key_region = region or "global"
    data = execute_aws_command(config['command'], f"{service}_{profile}_{cache_key_region}")
    
    is_error, error_items = handle_aws_response(data, profile)
    if is_error:
        return error_items
    
    items = config['extract_items'](data)
    if not items:
        return []
    
    results = []
    for item in items:
        item_data = config['get_item_data'](item)
        
        if search_str:
            search_lower = search_str.lower()
            if not (search_lower in (item_data['name'] or '').lower() or 
                   search_lower in (item_data['id'] or '').lower()):
                continue
        
        title = f"{service.upper()}: {item_data['name'] or item_data['id']}"
        destination_url = config['url_template'].format(**item_data, region=region)
        open_arg = config.get('open_arg', destination_url)
        
        log_arg = f"log_and_open::{open_arg}|{title}"
        
        mods = {
            "cmd": {
                "valid": True, "arg": destination_url,
                "subtitle": "⌘ Hold Cmd+Enter to copy URL to clipboard"
            }
        }
        
        results.append(generate_alfred_item(
            title=title,
            subtitle=f"{item_data['extra_info']} | Press Enter to open",
            arg=log_arg,
            uid=item_data.get('id') or item_data.get('name') or destination_url,
            mods=mods
        ))
    
    return results

def main():
    query_parts = query_str.split()
    num_parts = len(query_parts)
    alfred_items = []

    if num_parts > 0 and query_parts[0] == 'his':
        history_file = os.path.join(CACHE_DIR, "aws_history.log")
        if not os.path.exists(history_file):
            alfred_items.append(generate_alfred_item("No History", "You haven't opened any resources yet.", "no_history", "no_history", False))
        else:
            with open(history_file, 'r') as f:
                lines = f.readlines()
            
            seen_urls = set()
            search_term = " ".join(query_parts[1:]).lower() if num_parts > 1 else ""
            count = 0
            for line in reversed(lines):
                if count >= 50: break
                line = line.strip()
                if not line: continue
                
                if '|' not in line: continue
                url, title = line.rsplit('|', 1)
                
                if url in seen_urls: continue
                if search_term and search_term not in title.lower() and search_term not in url.lower(): continue

                seen_urls.add(url)
                alfred_items.append(generate_alfred_item(
                    title=title,
                    subtitle=f"Accessed recently. URL: {url}",
                    arg=url, uid=url, valid=True
                ))
                count += 1
        
        if not alfred_items:
            alfred_items.append(generate_alfred_item("No History Found", "No items match your query.", "no_history", "no_history", False))
    
    elif num_parts == 0 or (num_parts == 1 and not query_str.endswith(' ')):
        search = query_parts[0] if num_parts == 1 else ""
        for service, desc in AVAILABLE_SERVICES.items():
            if search.lower() in service.lower():
                alfred_items.append(generate_alfred_item(
                    title=f"Service: {service}", subtitle=f"Search for {desc}",
                    arg=service, uid=service, valid=False, autocomplete=f"{service} "
                ))
    
    elif num_parts == 1 and query_str.endswith(' '):
        service = query_parts[0]
        if service not in AVAILABLE_SERVICES or service == 'his':
            alfred_items.append(generate_status_item("service_not_supported", service=service))
        else:
            for profile, desc in AVAILABLE_PROFILES.items():
                alfred_items.append(generate_alfred_item(
                    title=f"Profile: {profile}", subtitle=f"Use the {desc}",
                    arg=f"{service} {profile}", uid=profile, valid=False, autocomplete=f"{service} {profile} "
                ))

    elif num_parts >= 2:
        service = query_parts[0]
        if service not in AVAILABLE_SERVICES:
            alfred_items.append(generate_status_item("service_not_supported", service=service))
        else:
            profile = query_parts[1]
            search_str = " ".join(query_parts[2:])

            if profile not in AVAILABLE_PROFILES:
                alfred_items.append(generate_status_item("profile_not_found", profile=profile))
            else:
                # 预检查 AWS 凭证状态
                if not check_aws_credentials(profile):
                    alfred_items.append(generate_status_item("credentials_invalid", profile=profile))
                else:
                    # 获取实际资源数据
                    region = get_region_for_profile(profile)
                    alfred_items = search_aws_resources(service, profile, region, search_str)
                    
                    # 如果没有资源数据，显示空结果提示
                    if not alfred_items:
                        alfred_items.append(generate_alfred_item(
                            title=f"No {service.upper()} resources found",
                            subtitle=f"No {service} resources match your search in {profile} profile",
                            arg="no-resources",
                            uid="no-resources",
                            valid=False
                        ))
    
    if not alfred_items:
        alfred_items.append(generate_alfred_item("No Results", "No items match your query", query_str, query_str, False))

    print(json.dumps({"items": alfred_items}))

if __name__ == "__main__":
    main()