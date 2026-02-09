#!/usr/bin/env bash

# Shell Aliases

# Navigation
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias ~='cd ~'

# List files
if command -v eza &> /dev/null; then
    # Modern replacement for ls (install with: brew install eza)
    alias ls='eza'
    alias ll='eza -lah'
    alias la='eza -a'
    alias lt='eza --tree'
else
    # Fallback to standard ls
    alias ll='ls -lah'
    alias la='ls -A'
fi

# Git aliases
alias g='git'
alias gs='git status'
alias ga='git add'
alias gaa='git add --all'
alias gc='git commit'
alias gcm='git commit -m'
alias gca='git commit --amend'
alias gco='git checkout'
alias gcb='git checkout -b'
alias gb='git branch'
alias gbd='git branch -d'
alias gd='git diff'
alias gdc='git diff --cached'
alias gl='git log --oneline --graph --decorate'
alias gp='git push'
alias gpl='git pull'
alias gf='git fetch'
alias gr='git rebase'
alias gm='git merge'
alias gst='git stash'
alias gstp='git stash pop'

# Docker aliases
alias d='docker'
alias dc='docker-compose'
alias dps='docker ps'
alias dpsa='docker ps -a'
alias di='docker images'
alias dex='docker exec -it'
alias drm='docker rm'
alias drmi='docker rmi'
alias dprune='docker system prune -af'

# Kubernetes aliases
alias k='kubectl'
alias kgp='kubectl get pods'
alias kgs='kubectl get services'
alias kgd='kubectl get deployments'
alias kd='kubectl describe'
alias kl='kubectl logs'
alias kaf='kubectl apply -f'
alias kdel='kubectl delete'
alias kctx='kubectl config current-context'
alias kns='kubectl config set-context --current --namespace'

# Go aliases
alias got='go test ./...'
alias gotv='go test -v ./...'
alias gob='go build'
alias gor='go run'
alias gom='go mod'
alias gomt='go mod tidy'
alias gofmt='gofmt -s -w .'
alias golint='golangci-lint run'

# Python aliases
alias py='python3'
alias pip='pip3'
alias venv='python3 -m venv'
alias activate='source venv/bin/activate'

# System utilities
alias grep='grep --color=auto'
alias mkdir='mkdir -p'
alias df='df -h'
alias du='du -h'
alias free='free -h'

# Safety aliases (prevent accidental deletion)
alias rm='rm -i'
alias cp='cp -i'
alias mv='mv -i'

# Network
alias ports='netstat -tulanp'
alias myip='curl ifconfig.me'
alias localip='ipconfig getifaddr en0'  # macOS

# File search
alias f='find . -name'
if command -v rg &> /dev/null; then
    alias search='rg'
else
    alias search='grep -r'
fi

# Processes
alias psg='ps aux | grep -v grep | grep -i -e VSZ -e'
alias topcpu='ps aux | sort -rk 3 | head -10'
alias topmem='ps aux | sort -rk 4 | head -10'

# Editor
alias vi='vim'
alias v='vim'

# Quick edits
alias zshrc='vim ~/.zshrc'
alias vimrc='vim ~/.vimrc'
alias gitconfig='vim ~/.gitconfig'
alias aliases='vim ~/dotfiles/shell/aliases.sh'

# Reload shell
alias reload='source ~/.zshrc'  # or ~/.bashrc for bash

# Directory shortcuts
alias dotfiles='cd ~/dotfiles'
alias projects='cd ~/projects'
alias downloads='cd ~/Downloads'

# Clipboard (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    alias pbcopy='pbcopy'
    alias pbpaste='pbpaste'
fi

# Clipboard (Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    alias pbcopy='xclip -selection clipboard'
    alias pbpaste='xclip -selection clipboard -o'
fi

# Misc
alias h='history'
alias c='clear'
alias e='exit'
alias path='echo $PATH | tr ":" "\n"'
alias now='date +"%Y-%m-%d %H:%M:%S"'
alias week='date +%V'

# Tailscale (if installed)
alias ts='tailscale'
alias tss='tailscale status'
alias tsup='tailscale up'
alias tsdown='tailscale down'

# Terraform (if used)
alias tf='terraform'
alias tfi='terraform init'
alias tfp='terraform plan'
alias tfa='terraform apply'
alias tfd='terraform destroy'

# Claude Code
alias claude='claude-code'
alias cc='claude-code'
