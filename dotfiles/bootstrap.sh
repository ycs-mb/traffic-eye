#!/usr/bin/env bash

# Dotfiles Bootstrap Script
# Installs dotfiles by creating symbolic links

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the dotfiles directory
DOTFILES_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo -e "${GREEN}Dotfiles Bootstrap${NC}"
echo "Installing dotfiles from: $DOTFILES_DIR"
echo ""

# Function to create symlink
link_file() {
    local src=$1
    local dst=$2

    if [ -L "$dst" ]; then
        echo -e "${YELLOW}Skipping${NC} $dst (already symlinked)"
    elif [ -f "$dst" ] || [ -d "$dst" ]; then
        echo -e "${YELLOW}Backing up${NC} $dst to ${dst}.backup"
        mv "$dst" "${dst}.backup"
        ln -sf "$src" "$dst"
        echo -e "${GREEN}Linked${NC} $src -> $dst"
    else
        ln -sf "$src" "$dst"
        echo -e "${GREEN}Linked${NC} $src -> $dst"
    fi
}

# Git configurations
echo -e "\n${GREEN}Installing Git configurations...${NC}"
if [ -d "$DOTFILES_DIR/git" ]; then
    link_file "$DOTFILES_DIR/git/.gitconfig" "$HOME/.gitconfig"
    link_file "$DOTFILES_DIR/git/.gitignore_global" "$HOME/.gitignore_global"
fi

# Shell configurations
echo -e "\n${GREEN}Installing Shell configurations...${NC}"
if [ -d "$DOTFILES_DIR/shell" ]; then
    link_file "$DOTFILES_DIR/shell/.bashrc" "$HOME/.bashrc"
    link_file "$DOTFILES_DIR/shell/.bash_profile" "$HOME/.bash_profile"
    link_file "$DOTFILES_DIR/shell/.zshrc" "$HOME/.zshrc"
fi

# Vim configurations
echo -e "\n${GREEN}Installing Vim configurations...${NC}"
if [ -d "$DOTFILES_DIR/vim" ]; then
    link_file "$DOTFILES_DIR/vim/.vimrc" "$HOME/.vimrc"
fi

# Claude Code configurations
echo -e "\n${GREEN}Installing Claude Code configurations...${NC}"
if [ -d "$DOTFILES_DIR/claude" ]; then
    mkdir -p "$HOME/.claude"
    link_file "$DOTFILES_DIR/claude/settings.json" "$HOME/.claude/settings.json"
    if [ -f "$DOTFILES_DIR/claude/keybindings.json" ]; then
        link_file "$DOTFILES_DIR/claude/keybindings.json" "$HOME/.claude/keybindings.json"
    fi
fi

# VS Code configurations
echo -e "\n${GREEN}Installing VS Code configurations...${NC}"
if [ -d "$DOTFILES_DIR/vscode" ]; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        mkdir -p "$HOME/Library/Application Support/Code/User"
        link_file "$DOTFILES_DIR/vscode/settings.json" "$HOME/Library/Application Support/Code/User/settings.json"
    else
        # Linux
        mkdir -p "$HOME/.config/Code/User"
        link_file "$DOTFILES_DIR/vscode/settings.json" "$HOME/.config/Code/User/settings.json"
    fi
fi

# SSH configuration (if exists)
echo -e "\n${GREEN}Installing SSH configurations...${NC}"
if [ -f "$DOTFILES_DIR/ssh/config" ]; then
    mkdir -p "$HOME/.ssh"
    link_file "$DOTFILES_DIR/ssh/config" "$HOME/.ssh/config"
    chmod 600 "$HOME/.ssh/config"
fi

# macOS specific settings
if [[ "$OSTYPE" == "darwin"* ]] && [ -f "$DOTFILES_DIR/macos/defaults.sh" ]; then
    echo -e "\n${GREEN}Would you like to apply macOS defaults? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        source "$DOTFILES_DIR/macos/defaults.sh"
    fi
fi

# Reload shell
echo -e "\n${GREEN}Installation complete!${NC}"
echo ""
echo "To reload your shell configuration, run:"
echo "  source ~/.zshrc    # for Zsh"
echo "  source ~/.bashrc   # for Bash"
echo ""
echo "Or restart your terminal."
