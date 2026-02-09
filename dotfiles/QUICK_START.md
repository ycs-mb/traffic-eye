# Dotfiles Quick Start Guide

## Installation Steps

### 1. Backup Existing Files (IMPORTANT!)
```bash
cd ~/dotfiles
./backup.sh
```

### 2. Review & Customize
```bash
# Update Git config with your details
vim git/.gitconfig
# Set name and email

# Customize shell configs
vim shell/.zshrc
vim shell/aliases.sh
```

### 3. Install Dotfiles
```bash
./bootstrap.sh
```

### 4. Reload Shell
```bash
# For Zsh
source ~/.zshrc

# For Bash
source ~/.bashrc
```

### 5. Verify Installation
```bash
# Check symbolic links
ls -la ~ | grep "^l"

# Test z.sh (after using a few directories)
z dotfiles

# Test aliases
ll
gs
```

## What's Included

### Shell Features
- **z.sh**: Smart directory jumping
  - `z dotfiles` - jump to ~/dotfiles
  - `z -l foo` - list matches for foo
- **Aliases**: 50+ useful shortcuts (ll, gs, gp, etc.)
- **Functions**: mkcd, extract, genpass, serve, etc.

### Git Configuration
- Colored output
- Useful aliases (st, co, lg, etc.)
- Global gitignore

### Vim Configuration
- Line numbers, syntax highlighting
- Smart indentation
- Persistent undo
- Custom key bindings

### Directory Structure
```
~/dotfiles/
├── git/           # Git configurations
├── shell/         # Shell configs (bash, zsh, z.sh)
├── vim/           # Vim config
├── claude/        # Claude Code settings
├── vscode/        # VS Code settings
└── macos/         # macOS specific settings
```

## Common Commands

### z.sh (Directory Navigation)
```bash
z foo           # Jump to most frecent directory matching foo
z -l foo        # List all matching directories
z -t foo        # Jump to most recently used
```

### Git Aliases
```bash
gs              # git status
ga .            # git add .
gcm "message"   # git commit -m "message"
gp              # git push
gl              # git log (pretty)
```

### Utilities
```bash
mkcd new-dir    # Create and cd into directory
extract file    # Extract any archive type
genpass 20      # Generate 20-char password
serve 8080      # Start HTTP server on port 8080
weather         # Show weather
```

## Syncing to New Machine

```bash
# 1. Clone repository
git clone https://github.com/yourusername/dotfiles.git ~/dotfiles

# 2. Run bootstrap
cd ~/dotfiles
./bootstrap.sh

# 3. Reload shell
source ~/.zshrc
```

## Updating Dotfiles

```bash
# Make changes
vim ~/dotfiles/shell/aliases.sh

# Test changes
source ~/.zshrc

# Commit and push
cd ~/dotfiles
git add shell/aliases.sh
git commit -m "Add new aliases"
git push
```

## Tips

1. **Test first**: Use `source ~/.zshrc` to test changes before committing
2. **Document**: Add comments to your configs
3. **Backup**: Always run `./backup.sh` before major changes
4. **Use .local files**: For machine-specific configs, use `~/.zshrc.local` (not committed)
5. **z.sh works better over time**: It learns your directory patterns

## Troubleshooting

### Links not working?
```bash
# Remove and recreate
rm ~/.zshrc
ln -sf ~/dotfiles/shell/.zshrc ~/.zshrc
```

### Changes not taking effect?
```bash
source ~/.zshrc  # Reload configuration
```

### z.sh not working?
```bash
# cd into directories a few times first
cd ~/projects
cd ~/dotfiles
cd ~/Downloads

# Then try z
z dot  # Should jump to dotfiles
```

## Next Steps

1. Install Homebrew: https://brew.sh
2. Install developer tools (git, vim, etc.)
3. Set up SSH keys
4. Configure Git user info
5. Install Oh My Zsh (optional)
6. Install fzf (fuzzy finder)
7. Explore and customize!

## Resources

- Full README: [README.md](README.md)
- z.sh docs: https://github.com/rupa/z
- Oh My Zsh: https://ohmyz.sh/
- Homebrew: https://brew.sh/
