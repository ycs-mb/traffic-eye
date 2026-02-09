# Dotfiles Setup Guide

A step-by-step guide to manage your dotfiles and set up a new development environment.

## Table of Contents

- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [Step-by-Step Setup](#step-by-step-setup)
- [What to Include](#what-to-include)
- [Maintenance](#maintenance)

## Overview

Dotfiles are configuration files for various tools and applications, typically starting with a dot (`.`). This repository helps you:
- Version control your configurations
- Sync settings across multiple machines
- Quickly bootstrap new development environments

## Directory Structure

```
dotfiles/
├── README.md           # This file
├── bootstrap.sh        # Installation script
├── backup.sh          # Backup existing dotfiles
├── git/               # Git configurations
│   ├── .gitconfig
│   └── .gitignore_global
├── shell/             # Shell configurations
│   ├── .bashrc
│   ├── .bash_profile
│   ├── .zshrc
│   └── aliases.sh
├── vim/               # Vim configurations
│   └── .vimrc
├── vscode/            # VS Code settings
│   └── settings.json
├── claude/            # Claude Code settings
│   ├── settings.json
│   └── keybindings.json
└── macos/             # macOS specific settings
    └── defaults.sh
```

## Step-by-Step Setup

### Step 1: Backup Existing Dotfiles

**IMPORTANT**: Always backup before making changes!

```bash
# Run the backup script
./backup.sh

# Or manually backup
mkdir -p ~/dotfiles_backup
cp ~/.bashrc ~/dotfiles_backup/.bashrc.bak
cp ~/.zshrc ~/dotfiles_backup/.zshrc.bak
cp ~/.gitconfig ~/dotfiles_backup/.gitconfig.bak
# ... backup other files
```

### Step 2: Clone or Initialize Repository

**Option A: First Time Setup**
```bash
cd ~/dotfiles
git init
git add .
git commit -m "Initial dotfiles commit"
git remote add origin git@github.com:yourusername/dotfiles.git
git push -u origin main
```

**Option B: Clone Existing Repository**
```bash
cd ~
git clone git@github.com:yourusername/dotfiles.git
cd dotfiles
```

### Step 3: Review and Customize

Before installing, review each configuration file:

```bash
# Check each file
cat git/.gitconfig
cat shell/.zshrc
cat shell/aliases.sh

# Customize as needed
vim git/.gitconfig  # Update name, email
vim shell/.zshrc    # Adjust paths, plugins
```

### Step 4: Run Bootstrap Script

```bash
# Make executable
chmod +x bootstrap.sh

# Run installation
./bootstrap.sh
```

The bootstrap script will:
1. Create symbolic links from dotfiles to your home directory
2. Source shell configurations
3. Install necessary tools (if configured)

### Step 5: Install Development Tools (Optional)

```bash
# Homebrew (macOS)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Common tools
brew install git
brew install vim
brew install tmux
brew install fzf
brew install ripgrep
brew install bat
brew install eza

# Language-specific tools
brew install go
brew install node
brew install python
```

### Step 6: Configure Git

```bash
# Set global Git config
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# Verify
git config --list
```

### Step 7: Reload Shell Configuration

```bash
# For Zsh
source ~/.zshrc

# For Bash
source ~/.bashrc
```

### Step 8: Verify Installation

```bash
# Check symbolic links
ls -la ~ | grep "^l"

# Test aliases
ll      # Should work if alias defined
gs      # Should work if git alias defined

# Verify Git config
git config --global --list
```

## What to Include

### Essential Files

- **Git**: `.gitconfig`, `.gitignore_global`
- **Shell**: `.bashrc`, `.zshrc`, `.bash_profile`
- **Vim**: `.vimrc`
- **SSH**: `config` (⚠️ Never commit private keys!)
- **Claude Code**: `~/.claude/settings.json`

### Common Configurations

```bash
# Shell aliases
alias ll='ls -lah'
alias gs='git status'
alias gd='git diff'
alias gc='git commit'
alias gp='git push'

# Environment variables
export EDITOR=vim
export GOPATH=$HOME/go
export PATH=$PATH:$GOPATH/bin

# Useful functions
mkcd() {
    mkdir -p "$1" && cd "$1"
}
```

### What NOT to Include

❌ **Never commit these:**
- API keys, tokens, passwords
- Private SSH keys
- `.env` files with secrets
- Company-specific credentials
- Personal identifying information

✅ **Use instead:**
- Environment variables
- Secret management tools (1Password, LastPass)
- `.env.example` templates
- Encrypted vaults

## Maintenance

### Adding New Dotfiles

```bash
# 1. Copy file to dotfiles repo
cp ~/.newconfig ~/dotfiles/tool/.newconfig

# 2. Commit
cd ~/dotfiles
git add tool/.newconfig
git commit -m "Add .newconfig for tool"
git push

# 3. Create symlink
ln -sf ~/dotfiles/tool/.newconfig ~/.newconfig
```

### Updating Configurations

```bash
# Edit in dotfiles repo
cd ~/dotfiles
vim shell/.zshrc

# Commit changes
git add shell/.zshrc
git commit -m "Update zsh configuration"
git push

# Reload
source ~/.zshrc
```

### Syncing to New Machine

```bash
# 1. Clone repository
git clone git@github.com:yourusername/dotfiles.git ~/dotfiles

# 2. Run bootstrap
cd ~/dotfiles
./bootstrap.sh

# 3. Install tools
brew bundle  # if using Brewfile
```

### Keeping Up to Date

```bash
# Pull latest changes
cd ~/dotfiles
git pull

# Re-run bootstrap if needed
./bootstrap.sh
```

## Tips and Best Practices

1. **Version Control**: Always commit and push changes
2. **Documentation**: Comment your configurations
3. **Modularity**: Separate configs by tool/purpose
4. **Testing**: Test on a VM or separate account first
5. **Privacy**: Never commit secrets
6. **Portability**: Use conditional logic for different OSes
7. **Backups**: Keep backups before major changes

## Example Workflow

```bash
# Daily usage
cd ~/dotfiles

# Make changes
vim shell/aliases.sh

# Test changes
source ~/.zshrc

# Commit if working
git add shell/aliases.sh
git commit -m "Add new kubectl aliases"
git push

# On another machine
cd ~/dotfiles
git pull
source ~/.zshrc
```

## Troubleshooting

### Symbolic links not working
```bash
# Check if link exists
ls -la ~/.zshrc

# Remove and recreate
rm ~/.zshrc
ln -sf ~/dotfiles/shell/.zshrc ~/.zshrc
```

### Changes not taking effect
```bash
# Reload shell
source ~/.zshrc  # or ~/.bashrc

# Or restart terminal
```

### Permission denied
```bash
# Make scripts executable
chmod +x bootstrap.sh
chmod +x backup.sh
```

## Resources

- [GitHub Dotfiles Guide](https://dotfiles.github.io/)
- [Awesome Dotfiles](https://github.com/webpro/awesome-dotfiles)
- [Mathias Bynens Dotfiles](https://github.com/mathiasbynens/dotfiles)

## License

MIT License - Feel free to use and modify for your own needs.
