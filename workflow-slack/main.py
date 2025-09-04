# -*- coding: utf-8 -*-
import sys
import json
import subprocess
import os

def load_config():
    """Load configuration from .env file"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    
    commands = {}
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # Skip comments and empty lines
                if not line or line.startswith('#'):
                    continue
                
                # Parse command=team_id,channel_id format
                if '=' in line:
                    command, value = line.split('=', 1)
                    command = command.strip()
                    value = value.strip()
                    
                    if ',' in value:
                        team_id, channel_id = value.split(',', 1)
                        commands[command] = {
                            'team_id': team_id.strip(),
                            'channel_id': channel_id.strip()
                        }
                    
        return commands
    except FileNotFoundError:
        print(f"Config file not found: {env_path}", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Error reading config file: {e}", file=sys.stderr)
        return {}

def open_slack_channel(team_id, channel_id):
    """Open Slack channel"""
    url = f"slack://channel?team={team_id}&id={channel_id}"
    try:
        subprocess.run(['open', url], check=True)
        return True
    except Exception as e:
        print(f"Failed to open Slack channel: {e}", file=sys.stderr)
        return False

def generate_alfred_results(query, commands):
    """Generate Alfred Script Filter results"""
    
    items = []
    
    for command, config in commands.items():
        # Filter by query if provided
        if query and query.lower() not in command.lower():
            continue
            
        team_id = config.get('team_id', '')
        channel_id = config.get('channel_id', '')
        
        subtitle = f"Open Slack channel (Team: {team_id[:8]}, Channel: {channel_id[:8]})"
        if not team_id or not channel_id:
            subtitle = "⚠️ Missing team_id or channel_id in configuration"
            
        items.append({
            'arg': command,
            'title': command,
            'subtitle': subtitle,
            'autocomplete': command
        })
    
    return {'items': items}

def handle_command(command, commands):
    """Handle the selected command"""
    if command not in commands:
        print(f"Unknown command: {command}", file=sys.stderr)
        return False
        
    config = commands[command]
    team_id = config.get("team_id")
    channel_id = config.get("channel_id")
    
    if not team_id or not channel_id:
        print(f"Missing team_id or channel_id for command: {command}", file=sys.stderr)
        return False
    
    # Open Slack channel
    return open_slack_channel(team_id, channel_id)

def main():
    """Main function"""
    # Load configuration
    commands = load_config()
    
    if len(sys.argv) > 1:
        # Command execution mode
        command = sys.argv[1]
        success = handle_command(command, commands)
        if not success:
            print(f"Failed to execute command: {command}", file=sys.stderr)
            sys.exit(1)
    else:
        # Alfred Script Filter mode
        query = os.environ.get('query', '').strip()
        results = generate_alfred_results(query, commands)
        print(json.dumps(results, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
