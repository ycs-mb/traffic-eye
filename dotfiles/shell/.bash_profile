# Bash Profile

# Load .bashrc if it exists
if [ -f ~/.bashrc ]; then
    source ~/.bashrc
fi

# macOS specific settings
if [[ "$OSTYPE" == "darwin"* ]]; then
    # Add Homebrew to PATH
    if [ -d "/opt/homebrew/bin" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    fi
fi
