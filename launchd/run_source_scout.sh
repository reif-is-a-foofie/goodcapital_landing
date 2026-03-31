#!/bin/zsh
# Wrapper for source_scout.py run via launchd.
# launchd does not inherit the user's shell environment.  We try several
# sources in priority order to pick up ANTHROPIC_API_KEY:
#
#   1. ~/.zshrc           — used for interactive shells on this machine
#   2. ~/.zprofile        — login-shell profile
#   3. ~/.zshenv          — always-sourced zsh env file
#   4. ~/.profile         — POSIX fallback
#   5. ~/.bash_profile    — bash login profile (sometimes shared)
#   6. ~/.secrets         — dedicated secrets file (recommended for launchd)
#   7. macOS Keychain     — via `security find-generic-password -s ANTHROPIC_API_KEY`
#
# NOTE: source_scout.py uses the web_search tool which requires a billing-attached
# API key (sk-ant-api...).  OAuth tokens from Claude Code do NOT work for this tool.
#
# To make this work permanently, use one of:
#   security add-generic-password -s ANTHROPIC_API_KEY -a ANTHROPIC_API_KEY -w sk-ant-api...
# OR:
#   echo 'export ANTHROPIC_API_KEY=sk-ant-api...' >> ~/.secrets

source "$HOME/.zshrc"       2>/dev/null || true
source "$HOME/.zprofile"    2>/dev/null || true
source "$HOME/.zshenv"      2>/dev/null || true
source "$HOME/.profile"     2>/dev/null || true
source "$HOME/.bash_profile" 2>/dev/null || true
source "$HOME/.secrets"     2>/dev/null || true

# Keychain fallback: only attempt if key is still missing
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    _key="$(security find-generic-password -s ANTHROPIC_API_KEY -w 2>/dev/null)"
    if [[ -n "$_key" ]]; then
        export ANTHROPIC_API_KEY="$_key"
    fi
fi

# Diagnostic: warn clearly if no auth is available so launchd logs are actionable.
if [[ -z "$ANTHROPIC_API_KEY" ]]; then
    echo "ERROR: ANTHROPIC_API_KEY is not set. source_scout.py requires a billing-attached" >&2
    echo "  Anthropic API key (sk-ant-api...). Store it in the macOS Keychain:" >&2
    echo "    security add-generic-password -s ANTHROPIC_API_KEY -a ANTHROPIC_API_KEY -w sk-ant-api..." >&2
    echo "  Or add 'export ANTHROPIC_API_KEY=sk-ant-api...' to ~/.secrets" >&2
fi

exec python3 /Users/reify/Classified/goodcapital_landing/source_scout.py
