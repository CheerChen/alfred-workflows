#!/bin/bash

# This script is intended to be pasted into the Alfred workflow's action script field.
# It handles opening AWS console URLs, logging them to a history file, and executing SSO login commands.

DATA_DIR="${alfred_workflow_data:-$HOME/.alfred_workflow_data}"
HISTORY_FILE="$DATA_DIR/aws_history.log"
mkdir -p "$DATA_DIR"

QUERY="{query}"

# Helper function to open URL in the correct Chrome profile
open_url() {
    # Read CHROME_PROFILE from .env file, default to "Default"
    PROFILE=$(awk -F= '/^CHROME_PROFILE=/ {print $2}' ".env" 2>/dev/null)
    open -a "Google Chrome" -n --args --profile-directory="${PROFILE:-Default}" "$1"
}

if [[ "$QUERY" == log_and_open::* ]]; then
    # This is a new resource being opened from a search result.
    # Format: log_and_open::URL|Title
    DATA_PART="${QUERY#*::}"
    
    # Append the data part to the history file.
    echo "$DATA_PART" >> "$HISTORY_FILE"

    # Extract URL (everything before the last '|')
    URL="${DATA_PART%|*}"
    
    open_url "$URL"

elif [[ "$QUERY" == http* ]]; then
    # This is an item from history being opened, or from an older version of the workflow.
    # Just open it, don't re-log it.
    open_url "$QUERY"

elif [[ "$QUERY" == aws* ]]; then
    # This is a command, e.g., for SSO login or a combined login+open command.
    echo "Executing: $QUERY"
    # The command is executed directly.
    eval $QUERY
fi
