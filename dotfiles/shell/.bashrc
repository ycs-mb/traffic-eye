# Bash Configuration

# If not running interactively, don't do anything
[[ $- != *i* ]] && return

# History configuration
HISTSIZE=10000
HISTFILESIZE=20000
HISTCONTROL=ignoreboth:erasedups
shopt -s histappend

# Update window size after each command
shopt -s checkwinsize

# Enable extended globbing
shopt -s globstar 2> /dev/null

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

# Homebrew configuration (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    if [[ -f "/opt/homebrew/bin/brew" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    elif [[ -f "/usr/local/bin/brew" ]]; then
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

# Enable programmable completion
if ! shopt -oq posix; then
  if [ -f /usr/share/bash-completion/bash_completion ]; then
    . /usr/share/bash-completion/bash_completion
  elif [ -f /etc/bash_completion ]; then
    . /etc/bash_completion
  fi
fi

# z.sh - jump around (directory navigation)
if [ -f "$HOME/dotfiles/shell/z.sh" ]; then
    source "$HOME/dotfiles/shell/z.sh"
fi

# fzf integration (if installed)
[ -f ~/.fzf.bash ] && source ~/.fzf.bash

# Simple colored prompt
PS1='\[\033[01;32m\]\u@\h\[\033[00m\]:\[\033[01;34m\]\w\[\033[00m\]\$ '

# Load local customizations (not committed to git)
if [ -f "$HOME/.bashrc.local" ]; then
    source "$HOME/.bashrc.local"
fi
