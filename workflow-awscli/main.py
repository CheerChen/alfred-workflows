# -*- coding: utf-8 -*-
import sys
import json
import subprocess
import os
import time

# --- ++ 新增配置：可用的服务和Profile ++ ---
# 在这里定义你的服务和Profile，以便脚本提供提示
AVAILABLE_SERVICES = {
    "ec2": " Elastic Compute Cloud (EC2) instances",
    "rds": " Relational Database Service (RDS) instances",
    "lambda": " Lambda functions",
    "dynamo": " DynamoDB tables",
    "sfn": " Step Functions",
    "secret": " Secrets Manager"
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
        result = subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL)
        data = json.loads(result)
        with open(cache_file, 'w') as f: json.dump(data, f)
        return data
    except (subprocess.CalledProcessError, json.JSONDecodeError): return None

def generate_alfred_item(title, subtitle, arg, uid, valid=True, autocomplete=None):
    item = {"uid": uid, "title": title, "subtitle": subtitle, "arg": arg, "valid": valid}
    if autocomplete: item["autocomplete"] = autocomplete
    return item

def get_tag_name(tags):
    if not tags: return ""
    for tag in tags:
        if tag.get('Key') == 'Name': return tag.get('Value', '')
    return ""

def search_ec2(profile, region, search_str):
    command = ['aws', 'ec2', 'describe-instances', '--profile', profile, '--region', region, '--query', 'Reservations[].Instances[]']
    instances = execute_aws_command(command, f"ec2_{profile}")
    results = []
    if not instances: return results
    for inst in instances:
        instance_id = inst.get('InstanceId', 'N/A')
        name = get_tag_name(inst.get('Tags', []))
        if not search_str or search_str.lower() in name.lower() or search_str.lower() in instance_id.lower():
            results.append(generate_alfred_item(f"EC2: {name or instance_id}", f"ID: {instance_id} | State: {inst.get('State', {}).get('Name', 'N/A')}", f"https://{region}.console.aws.amazon.com/ec2/v2/home?region={region}#InstanceDetails:instanceId={instance_id}", instance_id))
    return results

def search_rds(profile, region, search_str):
    command = ['aws', 'rds', 'describe-db-instances', '--profile', profile, '--region', region, '--query', 'DBInstances[]']
    databases = execute_aws_command(command, f"rds_{profile}")
    results = []
    if not databases: return results
    for db in databases:
        db_id = db.get('DBInstanceIdentifier')
        if not search_str or search_str.lower() in db_id.lower():
            results.append(generate_alfred_item(f"RDS: {db_id}", f"Status: {db.get('DBInstanceStatus')} | Engine: {db.get('Engine')}", f"https://{region}.console.aws.amazon.com/rds/home?region={region}#database:id={db_id};is-cluster=false", db_id))
    return results

# 其他 search_xxx 函数与之前版本相同，为简洁省略，实际代码中应保留
def search_lambda(profile, region, search_str):
    command = ['aws', 'lambda', 'list-functions', '--profile', profile, '--region', region, '--query', 'Functions[]']
    functions = execute_aws_command(command, f"lambda_{profile}")
    results = []
    if not functions: return results
    for func in functions:
        func_name = func.get('FunctionName')
        if not search_str or search_str.lower() in func_name.lower():
            results.append(generate_alfred_item(f"Lambda: {func_name}", f"Runtime: {func.get('Runtime')}", f"https://{region}.console.aws.amazon.com/lambda/home?region={region}#/functions/{func_name}?tab=code", func_name))
    return results

def search_dynamodb(profile, region, search_str):
    command = ['aws', 'dynamodb', 'list-tables', '--profile', profile, '--region', region, '--query', 'TableNames[]']
    table_names = execute_aws_command(command, f"dynamodb_{profile}")
    results = []
    if not table_names: return results
    for name in table_names:
        if not search_str or search_str.lower() in name.lower():
            results.append(generate_alfred_item(f"DynamoDB: {name}", f"Table Name: {name}", f"https://{region}.console.aws.amazon.com/dynamodbv2/home?region={region}#table?name={name}&tab=overview", name))
    return results
    
def search_sfn(profile, region, search_str):
    command = ['aws', 'stepfunctions', 'list-state-machines', '--profile', profile, '--region', region, '--query', 'stateMachines[]']
    machines = execute_aws_command(command, f"sfn_{profile}")
    results = []
    if not machines: return results
    for machine in machines:
        name, arn = machine.get('name'), machine.get('stateMachineArn')
        if not search_str or search_str.lower() in name.lower():
            results.append(generate_alfred_item(f"Step Function: {name}", f"ARN: {arn}", f"https://{region}.console.aws.amazon.com/states/home?region={region}#/statemachines/view/{arn}", arn))
    return results

def search_secret(profile, region, search_str):
    command = ['aws', 'secretsmanager', 'list-secrets', '--profile', profile, '--region', region, '--query', 'SecretList[]']
    secrets = execute_aws_command(command, f"secret_{profile}")
    results = []
    if not secrets: return results
    for secret in secrets:
        name = secret.get('Name')
        if not search_str or search_str.lower() in name.lower():
            results.append(generate_alfred_item(f"Secret: {name}", f"Secret Name: {name}", f"https://{region}.console.aws.amazon.com/secretsmanager/secret?name={name}&region={region}", name))
    return results
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
                'secret': search_secret
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