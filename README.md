# Alfred Workflows

A collection of useful Alfred workflows for productivity enhancement.

## Installation

This repository provides an installation script that creates symbolic links from your workflow folders to Alfred's workflows directory, allowing you to keep your workflows in version control while having them available in Alfred.

### Quick Setup

1. Clone this repository:

   ```bash
   git clone https://github.com/CheerChen/alfred-workflows.git
   cd alfred-workflows
   ```

2. Run the installation script:

   ```bash
   ./install.sh
   ```

The script will:

- Automatically detect your Alfred workflows directory (including custom sync folders)
- Create symbolic links for all `workflow-*` directories
- Allow you to update workflows by simply pulling changes from git

### How it works

The `install.sh` script:

1. Reads Alfred's preferences to find the correct workflows directory
2. Iterates through all folders starting with `workflow-`
3. Creates symbolic links in Alfred's workflows directory
4. Can be safely re-run to update existing links

## Available Workflows

- **workflow-acli**: AWS CLI utilities
- **workflow-awscli**: Extended AWS CLI functionality  
- **workflow-gh**: GitHub CLI integration
- **workflow-katakana**: Japanese katakana conversion tools

## Usage

After installation, the workflows will appear in Alfred and can be used immediately.

### Configuration

Each workflow that requires configuration uses `.env` files for environment-specific settings. This keeps your personal configuration separate from the git repository.

To configure a workflow:

1. Navigate to the workflow directory (e.g., `workflow-acli/`)
2. Copy `.env.example` to `.env`:

   ```bash
   cp .env.example .env
   ```

3. Edit the `.env` file with your specific values:

### Updating Workflows

To update workflows:

```bash
git pull
# No need to re-run install.sh unless new workflows are added
```

## Development

To add a new workflow:

1. Create a new folder with the prefix `workflow-`
2. Add your Alfred workflow files (info.plist, main.py, etc.)
3. Run `./install.sh` to create the symbolic link
4. The workflow will appear in Alfred

## Requirements

- macOS
- Alfred with Powerpack
- Git (for cloning and updates)
