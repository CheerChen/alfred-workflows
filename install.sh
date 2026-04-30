#!/bin/bash

# --- Configuration ---
# Git repository root directory (where this script is located)
SOURCE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# --- 1. Homebrew prerequisite ---
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew is not installed."
    echo "   Install it first: https://brew.sh"
    exit 1
fi
echo "✅ Homebrew detected ($(brew --prefix))"

# --- 2. Locate Alfred's workflows directory ---
ALFRED_PREFS_PATH=$(plutil -p ~/Library/Preferences/com.runningwithcrayons.Alfred-Preferences.plist 2>/dev/null | awk -F '"' '/syncfolder/{print $2}')
if [ -z "$ALFRED_PREFS_PATH" ]; then
    ALFRED_PREFS_PATH="$HOME/Library/Application Support/Alfred"
fi
ALFRED_PREFS_PATH=$(eval echo "$ALFRED_PREFS_PATH")
WORKFLOW_DIR="${ALFRED_PREFS_PATH}/Alfred.alfredpreferences/workflows"

if [ ! -d "$WORKFLOW_DIR" ]; then
    echo "❌ Alfred Workflow directory not found: ${WORKFLOW_DIR}"
    exit 1
fi

echo "✅ Alfred Workflow directory: ${WORKFLOW_DIR}"
echo "✅ Source directory:          ${SOURCE_DIR}"
echo "--------------------------------------------------"

# --- 3. CLI → install command mapping (adjust as needed) ---
install_cli() {
    case "$1" in
        aws)  brew install awscli ;;
        gh)   brew install gh ;;
        jq)   brew install jq ;;
        acli) brew tap atlassian/homebrew-acli && brew install acli ;;
        *)    echo "❌ Don't know how to install '$1'"; return 1 ;;
    esac
}

# Candidate CLIs we know how to detect/install. Add more here if new workflows
# pull in additional command-line tools.
CANDIDATE_CLIS=(aws acli gh jq)
MISSING_CLIS=()

# --- 4. Link each workflow & scan its scripts for CLI deps ---
for workflow in "$SOURCE_DIR"/workflow-*; do
    [ -d "$workflow" ] || continue
    BASENAME=$(basename "$workflow")
    DEST_PATH="${WORKFLOW_DIR}/${BASENAME}"

    echo "🔗 Linking ${BASENAME}..."
    # -s symlink, -f force overwrite, -n treat dest as file (avoid nesting)
    ln -sfn "$workflow" "$DEST_PATH"
    echo "   -> ${workflow} -> ${DEST_PATH}"

    for cli in "${CANDIDATE_CLIS[@]}"; do
        # Word-boundary-ish match: cli surrounded by non-identifier chars or string delimiters.
        if grep -rEq "(^|[^a-zA-Z0-9_])${cli}([^a-zA-Z0-9_]|$)" \
              "$workflow" --include='*.py' --include='*.sh' --include='*.plist' 2>/dev/null; then
            if command -v "$cli" &> /dev/null; then
                echo "   ✅ requires '${cli}' — already installed ($(command -v "$cli"))"
            else
                echo "   ⚠️  requires '${cli}' — NOT installed"
                MISSING_CLIS+=("${cli}")
            fi
        fi
    done
done

echo "--------------------------------------------------"
echo "🎉 All workflows linked."

# --- 5. Auto-install missing dependencies ---
if [ ${#MISSING_CLIS[@]} -gt 0 ]; then
    # Deduplicate
    UNIQUE_MISSING=($(printf '%s\n' "${MISSING_CLIS[@]}" | sort -u))
    echo ""
    echo "📦 Missing CLIs: ${UNIQUE_MISSING[*]}"
    read -r -p "   Install them now via Homebrew? [Y/n] " reply
    reply=${reply:-Y}
    if [[ "$reply" =~ ^[Yy]$ ]]; then
        for cli in "${UNIQUE_MISSING[@]}"; do
            echo ""
            echo "📥 Installing ${cli}..."
            install_cli "$cli" || echo "❌ Failed to install ${cli}"
        done
    else
        echo "Skipped. Install later with install.sh or manually."
    fi
fi
