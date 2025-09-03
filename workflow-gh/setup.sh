#!/bin/bash

machine="$(/usr/bin/uname -m)"

if [[ "${machine}" == "arm64" ]]; then
  prefix="/opt/homebrew"
else
  prefix="/usr/local"
fi

export PATH="$prefix/bin:$PATH"

# Load environment variables from .env file
WORKFLOW_DIR="$(dirname "$0")"
ENV_FILE="$WORKFLOW_DIR/.env"

if [ -f "$ENV_FILE" ]; then
    while IFS='=' read -r key value; do
        # Remove comments and empty lines
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)
        if [[ ! "$key" =~ ^# ]] && [[ -n "$key" ]] && [[ -n "$value" ]]; then
            export "$key"="$value"
        fi
    done < "$ENV_FILE"
fi

# Set defaults if not loaded from .env
export API_HOST=${API_HOST:-github.com}
export CACHE_PULLS=${CACHE_PULLS:-10m}
export CACHE_SEARCH_REPOS=${CACHE_SEARCH_REPOS:-24h}
export CACHE_USER_REPOS=${CACHE_USER_REPOS:-72h}
export CHROME_PROFILE=${CHROME_PROFILE:-Default}

if ! command -v gh &> /dev/null; then
  open "https://github.com/edgarjs/github-repos-alfred-workflow/blob/master/README.md"
  exit 0
fi
