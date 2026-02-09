# Step-by-Step Installation Guide

## Prerequisites

- macOS, Linux, or WSL2
- Terminal access
- Git installed
- Bash or Zsh shell

## Step 1: Backup Existing Dotfiles ⚠️

**CRITICAL**: Always backup before making changes!

```bash
cd ~/dotfiles
./backup.sh
```

Your files will be backed up to: `~/dotfiles_backup_YYYYMMDD_HHMMSS/`

## Step 2: Review Configurations

Before installing, customize these files:

### Git Configuration (REQUIRED)
```bash
vim git/.gitconfig
```

Update:
- `name = Your Name`
- `email = your.email@example.com`

### Shell Configuration (Optional)
```bash
# Review and customize
vim shell/.zshrc          # Zsh configuration
vim shell/aliases.sh      # Shell aliases
vim shell/functions.sh    # Shell functions
```

### SSH Configuration (Optional)
```bash
vim ssh/config
```

Update with your SSH hosts and keys.

## Step 3: Run Bootstrap Script

This will create symbolic links from `~/dotfiles` to your home directory:

```bash
cd ~/dotfiles
./bootstrap.sh
```

The script will:
- ✅ Create symlinks for all dotfiles
- ✅ Backup existing files (if any)
- ✅ Set up directory structure
- ✅ Configure permissions

## Step 4: Reload Shell Configuration

```bash
# For Zsh users
source ~/.zshrc

# For Bash users
source ~/.bashrc

# Or restart your terminal
```

## Step 5: Verify Installation

### Check Symlinks
```bash
ls -la ~ | grep "^l"
```

You should see symlinks pointing to `~/dotfiles/`

### Test Git Configuration
```bash
git config --global --list
```

Should show your name and email.

### Test Shell Aliases
```bash
ll           # Should list files (long format)
gs           # Should show git status in a git repo
```

### Test z.sh (After Using Directories)
```bash
# Navigate to a few directories first
cd ~/Downloads
cd ~/dotfiles
cd ~/Documents

# Then test z
z dot        # Should jump to dotfiles
z -l down    # Should list Downloads
```

## Step 6: Optional Setup

### Install Homebrew (macOS)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Install Essential Tools
```bash
brew install git
brew install vim
brew install fzf
brew install ripgrep
brew install bat
brew install eza
brew install tmux
```

### Install Oh My Zsh (Optional)
```bash
sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)"
```

### Apply macOS Defaults (macOS Only)
```bash
cd ~/dotfiles
./macos/defaults.sh
```

**Note**: This will modify system settings. Review the script first!

## Step 7: Initialize Git Repository

If you want to version control your dotfiles:

```bash
cd ~/dotfiles
git init
git add .
git commit -m "Initial dotfiles setup"

# Optional: Push to GitHub
git remote add origin git@github.com:yourusername/dotfiles.git
git push -u origin main
```

## Step 8: Customize Further

### Add Machine-Specific Configuration

For settings that shouldn't be committed (like work-specific paths):

```bash
# Create local config files (not tracked by git)
touch ~/.zshrc.local
touch ~/.bashrc.local

# Add machine-specific settings
echo 'export WORK_DIR="/path/to/work"' >> ~/.zshrc.local
```

## Verification Checklist

- [ ] Backup created successfully
- [ ] Git configuration updated with your info
- [ ] Bootstrap script ran without errors
- [ ] Symlinks created in home directory
- [ ] Shell reloaded successfully
- [ ] Git aliases work (`gs`, `gl`, etc.)
- [ ] Shell aliases work (`ll`, etc.)
- [ ] z.sh works after navigating directories
- [ ] Vim configuration loaded (`:echo $MYVIMRC` in vim)

## Troubleshooting

### Symlink Issues

**Problem**: Symlink not created or wrong target

**Solution**:
```bash
# Remove bad symlink
rm ~/.zshrc

# Create correct symlink
ln -sf ~/dotfiles/shell/.zshrc ~/.zshrc
```

### Configuration Not Loading

**Problem**: Changes not taking effect

**Solution**:
```bash
# Reload shell
source ~/.zshrc

# Or restart terminal
```

### z.sh Not Working

**Problem**: `z` command not found or doesn't jump

**Solution**:
```bash
# 1. Check if z.sh is sourced
grep "z.sh" ~/.zshrc

# 2. Make sure you've navigated to directories first
cd ~/Downloads
cd ~/dotfiles
cd ~/Documents

# 3. Check z database
cat ~/.z

# 4. Try again
z dot
```

### Permission Denied

**Problem**: Scripts not executable

**Solution**:
```bash
chmod +x ~/dotfiles/bootstrap.sh
chmod +x ~/dotfiles/backup.sh
chmod +x ~/dotfiles/macos/defaults.sh
```

### Git Configuration Not Working

**Problem**: Git doesn't recognize your settings

**Solution**:
```bash
# Check if symlink exists
ls -la ~/.gitconfig

# Verify content
cat ~/.gitconfig

# Manually set if needed
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

## Updating Dotfiles

### Make Changes
```bash
cd ~/dotfiles
vim shell/aliases.sh
```

### Test Changes
```bash
source ~/.zshrc
```

### Commit Changes
```bash
cd ~/dotfiles
git add shell/aliases.sh
git commit -m "Add new aliases for Docker"
git push
```

### Pull Updates on Another Machine
```bash
cd ~/dotfiles
git pull
source ~/.zshrc
```

## Uninstalling

If you want to remove dotfiles and restore backups:

```bash
# Remove symlinks
rm ~/.zshrc ~/.bashrc ~/.gitconfig ~/.vimrc

# Restore from backup
cp ~/dotfiles_backup_*/. ~

# Remove dotfiles directory
rm -rf ~/dotfiles
```

## Next Steps

1. ✅ Complete installation
2. 📝 Customize configurations for your workflow
3. 🔧 Install additional tools (fzf, ripgrep, etc.)
4. 🌐 Push to GitHub for backup
5. 💻 Clone and install on other machines
6. 🎨 Explore and enjoy your new setup!

## Support

- 📖 Full documentation: [README.md](README.md)
- 🚀 Quick start: [QUICK_START.md](QUICK_START.md)
- 💡 Issues: Check troubleshooting section above

## Resources

- [Dotfiles Guide](https://dotfiles.github.io/)
- [Awesome Dotfiles](https://github.com/webpro/awesome-dotfiles)
- [z.sh Documentation](https://github.com/rupa/z)
- [Oh My Zsh](https://ohmyz.sh/)
