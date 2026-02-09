#!/usr/bin/env bash

# Shell Functions

# Create directory and cd into it
mkcd() {
    mkdir -p "$1" && cd "$1"
}

# Extract various archive types
extract() {
    if [ -f "$1" ]; then
        case "$1" in
            *.tar.bz2)   tar xjf "$1"     ;;
            *.tar.gz)    tar xzf "$1"     ;;
            *.bz2)       bunzip2 "$1"     ;;
            *.rar)       unrar x "$1"     ;;
            *.gz)        gunzip "$1"      ;;
            *.tar)       tar xf "$1"      ;;
            *.tbz2)      tar xjf "$1"     ;;
            *.tgz)       tar xzf "$1"     ;;
            *.zip)       unzip "$1"       ;;
            *.Z)         uncompress "$1"  ;;
            *.7z)        7z x "$1"        ;;
            *)           echo "'$1' cannot be extracted via extract()" ;;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}

# Find file by name
findfile() {
    find . -type f -iname "*$1*"
}

# Find directory by name
finddir() {
    find . -type d -iname "*$1*"
}

# Create backup of file
backup() {
    cp "$1"{,.bak}
}

# Git clone and cd into directory
gclone() {
    git clone "$1" && cd "$(basename "$1" .git)"
}

# Create new Go project structure
gonew() {
    if [ -z "$1" ]; then
        echo "Usage: gonew <project-name>"
        return 1
    fi

    mkdir -p "$1"/{cmd,internal,pkg,test}
    cd "$1"
    go mod init "$1"
    touch README.md
    echo "Created Go project: $1"
}

# Show disk usage of current directory
duh() {
    du -sh * | sort -h
}

# Process lookup
pgrep-full() {
    ps aux | grep -i "$1" | grep -v grep
}

# Kill process by name
pkill-name() {
    ps aux | grep -i "$1" | grep -v grep | awk '{print $2}' | xargs kill -9
}

# Show listening ports
listening() {
    if [ "$1" ]; then
        lsof -iTCP -sTCP:LISTEN -n -P | grep "$1"
    else
        lsof -iTCP -sTCP:LISTEN -n -P
    fi
}

# Weather (requires curl)
weather() {
    local city="${1:-}"
    curl "wttr.in/${city}"
}

# Cheat sheet (requires curl)
cheat() {
    curl "cheat.sh/$1"
}

# Generate random password
genpass() {
    local length="${1:-20}"
    LC_ALL=C tr -dc 'A-Za-z0-9!@#$%^&*' < /dev/urandom | head -c "$length"
    echo
}

# Quick HTTP server
serve() {
    local port="${1:-8000}"
    python3 -m http.server "$port"
}

# Git commit with conventional commit message
gcm-feat() {
    git commit -m "feat: $*"
}

gcm-fix() {
    git commit -m "fix: $*"
}

gcm-docs() {
    git commit -m "docs: $*"
}

gcm-refactor() {
    git commit -m "refactor: $*"
}

gcm-test() {
    git commit -m "test: $*"
}

# Docker helpers
dsh() {
    docker exec -it "$1" /bin/sh
}

dbash() {
    docker exec -it "$1" /bin/bash
}

dlogs() {
    docker logs -f "$1"
}

# Kubernetes helpers
kexec() {
    kubectl exec -it "$1" -- /bin/sh
}

klogs() {
    kubectl logs -f "$1"
}

# Update all Git repositories in current directory
git-update-all() {
    for dir in */; do
        if [ -d "$dir/.git" ]; then
            echo "Updating $dir..."
            (cd "$dir" && git pull)
        fi
    done
}

# Count lines of code
loc() {
    find . -type f \( -name "*.go" -o -name "*.py" -o -name "*.js" -o -name "*.ts" \) \
        -not -path "*/node_modules/*" \
        -not -path "*/vendor/*" \
        -not -path "*/.git/*" \
        | xargs wc -l | sort -n
}

# Show PATH entries one per line
path-list() {
    echo "$PATH" | tr ':' '\n'
}

# Add to PATH (no duplicates)
path-add() {
    if [ -d "$1" ] && [[ ":$PATH:" != *":$1:"* ]]; then
        export PATH="$1:$PATH"
    fi
}

# Copy file content to clipboard
ccp() {
    cat "$1" | pbcopy
}

# Copy current working directory to clipboard
cpwd() {
    pwd | pbcopy
    echo "$(pwd) copied to clipboard"
}
