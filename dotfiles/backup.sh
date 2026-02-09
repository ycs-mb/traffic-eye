#!/usr/bin/env bash

# Dotfiles Backup Script
# Backs up existing dotfiles before installation

set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Backup directory with timestamp
BACKUP_DIR="$HOME/dotfiles_backup_$(date +%Y%m%d_%H%M%S)"

echo -e "${GREEN}Dotfiles Backup${NC}"
echo "Backing up existing dotfiles to: $BACKUP_DIR"
echo ""

# Create backup directory
mkdir -p "$BACKUP_DIR"

# List of files to backup
FILES=(
    ".bashrc"
    ".bash_profile"
    ".zshrc"
    ".gitconfig"
    ".gitignore_global"
    ".vimrc"
    ".tmux.conf"
)

# Backup each file if it exists
for file in "${FILES[@]}"; do
    if [ -f "$HOME/$file" ] || [ -L "$HOME/$file" ]; then
        cp -P "$HOME/$file" "$BACKUP_DIR/"
        echo -e "${GREEN}Backed up${NC} $file"
    else
        echo -e "${YELLOW}Skipping${NC} $file (not found)"
    fi
done

# Backup .ssh/config if exists
if [ -f "$HOME/.ssh/config" ]; then
    mkdir -p "$BACKUP_DIR/.ssh"
    cp "$HOME/.ssh/config" "$BACKUP_DIR/.ssh/"
    echo -e "${GREEN}Backed up${NC} .ssh/config"
fi

# Backup Claude Code settings if exists
if [ -f "$HOME/.claude/settings.json" ]; then
    mkdir -p "$BACKUP_DIR/.claude"
    cp "$HOME/.claude/settings.json" "$BACKUP_DIR/.claude/"
    echo -e "${GREEN}Backed up${NC} .claude/settings.json"
fi

# Backup VS Code settings if exists
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    VSCODE_SETTINGS="$HOME/Library/Application Support/Code/User/settings.json"
    if [ -f "$VSCODE_SETTINGS" ]; then
        mkdir -p "$BACKUP_DIR/vscode"
        cp "$VSCODE_SETTINGS" "$BACKUP_DIR/vscode/"
        echo -e "${GREEN}Backed up${NC} VS Code settings"
    fi
else
    # Linux
    VSCODE_SETTINGS="$HOME/.config/Code/User/settings.json"
    if [ -f "$VSCODE_SETTINGS" ]; then
        mkdir -p "$BACKUP_DIR/vscode"
        cp "$VSCODE_SETTINGS" "$BACKUP_DIR/vscode/"
        echo -e "${GREEN}Backed up${NC} VS Code settings"
    fi
fi

echo ""
echo -e "${GREEN}Backup complete!${NC}"
echo "Backup location: $BACKUP_DIR"
echo ""
echo "To restore a file:"
echo "  cp $BACKUP_DIR/.bashrc ~/.bashrc"
