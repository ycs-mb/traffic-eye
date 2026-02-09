# Zsh Configuration

# Path to your oh-my-zsh installation (if using)
# export ZSH="$HOME/.oh-my-zsh"

# Set name of the theme to load
ZSH_THEME="agnoster"

# Enable command auto-correction
ENABLE_CORRECTION="true"

# Display red dots whilst waiting for completion
COMPLETION_WAITING_DOTS="true"

# History configuration
HISTFILE=~/.zsh_history
HISTSIZE=10000
SAVEHIST=10000
setopt SHARE_HISTORY
setopt HIST_IGNORE_DUPS
setopt HIST_IGNORE_ALL_DUPS
setopt HIST_SAVE_NO_DUPS
setopt HIST_REDUCE_BLANKS

# Environment variables
export EDITOR='vim'
export VISUAL='vim'
export PAGER='less'

# Language
export LANG=en_US.UTF-8
export LC_ALL=en_US.UTF-8

# Path configuration
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# Go configuration
export GOPATH="$HOME/go"
export PATH="$PATH:$GOPATH/bin"

# Node.js configuration (if using nvm)
# export NVM_DIR="$HOME/.nvm"
# [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"

# Homebrew configuration (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    # For M1 Macs
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
    # For Intel Macs
    if [[ -f "/usr/local/bin/brew" ]]; then
        eval "$(/usr/local/bin/brew shellenv)"
    fi
fi

# Load aliases
if [ -f "$HOME/dotfiles/shell/aliases.sh" ]; then
    source "$HOME/dotfiles/shell/aliases.sh"
fi

# Load custom functions
if [ -f "$HOME/dotfiles/shell/functions.sh" ]; then
    source "$HOME/dotfiles/shell/functions.sh"
fi

# Load plugins (oh-my-zsh)
# plugins=(git docker kubectl golang)
# source $ZSH/oh-my-zsh.sh

# z.sh - jump around (directory navigation)
if [ -f "$HOME/dotfiles/shell/z.sh" ]; then
    source "$HOME/dotfiles/shell/z.sh"
fi

# fzf integration (if installed)
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# Custom prompt (simple example)
PROMPT='%F{cyan}%~%f %F{green}❯%f '

# Enable autosuggestions (if installed)
# source /usr/local/share/zsh-autosuggestions/zsh-autosuggestions.zsh

# Enable syntax highlighting (if installed)
# source /usr/local/share/zsh-syntax-highlighting/zsh-syntax-highlighting.zsh

# Auto-completion
autoload -Uz compinit
compinit

# Case-insensitive completion
zstyle ':completion:*' matcher-list 'm:{a-zA-Z}={A-Za-z}'

# Colored completion
zstyle ':completion:*' list-colors "${(s.:.)LS_COLORS}"

# Enable Vi mode (optional)
# bindkey -v

# Key bindings
bindkey '^R' history-incremental-search-backward
bindkey '^A' beginning-of-line
bindkey '^E' end-of-line

# Load local customizations (not committed to git)
if [ -f "$HOME/.zshrc.local" ]; then
    source "$HOME/.zshrc.local"
fi
export PATH="$HOME/.local/bin:$PATH"
