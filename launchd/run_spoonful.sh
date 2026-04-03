#!/bin/zsh
# Wrapper for spoonful.py run via launchd.
# Picks up ANTHROPIC_API_KEY from env files or macOS Keychain.

source "$HOME/.zshrc"        2>/dev/null || true
source "$HOME/.zprofile"     2>/dev/null || true
source "$HOME/.zshenv"       2>/dev/null || true
source "$HOME/.profile"      2>/dev/null || true
source "$HOME/.bash_profile" 2>/dev/null || true
source "$HOME/.secrets"      2>/dev/null || true

if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    _key="$(security find-generic-password -s ANTHROPIC_API_KEY -a ANTHROPIC_API_KEY -w 2>/dev/null)"
    if [[ -n "$_key" ]]; then
        export ANTHROPIC_API_KEY="$_key"
    fi
fi

if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    echo "spoonful: ANTHROPIC_API_KEY not found — skipping run" >&2
    exit 1
fi

exec python3 /Users/reify/Classified/goodcapital_landing/lds_pipeline/spoonful.py --batch 30
