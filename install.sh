#!/bin/bash

# --- Configuration ---
# Git repository root directory (where this script is located)
SOURCE_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Automatically find Alfred's workflows directory
# First read Alfred's sync configuration
ALFRED_PREFS_PATH=$(plutil -p ~/Library/Preferences/com.runningwithcrayons.Alfred-Preferences.plist | grep syncfolder | awk -F '"' '{print $2}')

# If sync is not configured, use default path
if [ -z "$ALFRED_PREFS_PATH" ]; then
    ALFRED_PREFS_PATH="~/Library/Application Support/Alfred"
fi

# Expand ~ symbol
ALFRED_PREFS_PATH=$(eval echo "$ALFRED_PREFS_PATH")
WORKFLOW_DIR="${ALFRED_PREFS_PATH}/Alfred.alfredpreferences/workflows"

# Check if Workflows directory exists
if [ ! -d "$WORKFLOW_DIR" ]; then
    echo "❌ Alfred Workflow directory not found: ${WORKFLOW_DIR}"
    exit 1
fi

echo "✅ Alfred Workflow directory: ${WORKFLOW_DIR}"
echo "✅ Source directory: ${SOURCE_DIR}"
echo "--------------------------------------------------"

# --- Start linking ---
# Iterate through all folders starting with 'workflow-'
for workflow in "$SOURCE_DIR"/workflow-*; do
    if [ -d "$workflow" ]; then
        BASENAME=$(basename "$workflow")
        DEST_PATH="${WORKFLOW_DIR}/${BASENAME}"
        
        echo "🔗 Linking ${BASENAME}..."

        # Create symbolic link
        # -s: create symbolic link
        # -f: force overwrite if target exists (for re-running the script)
        # -n: treat target as normal file (safety option to prevent accidental directory entry)
        ln -sfn "$workflow" "$DEST_PATH"
        
        echo "   -> Link successful: ${workflow} -> ${DEST_PATH}"
    fi
done

echo "--------------------------------------------------"
echo "🎉 All workflows have been successfully linked!"

# Optional: Handle Python dependencies
# If your Python workflow has requirements.txt, you can add automatic installation logic here
# for workflow in "$SOURCE_DIR"/workflow-*; do
#     if [ -f "$workflow/requirements.txt" ]; then
#         echo "🐍 Installing dependencies for $(basename "$workflow")..."
#         pip3 install -r "$workflow/requirements.txt"
#     fi
# done