#!/bin/zsh
# Wrapper for source_scout.py run via launchd.
# launchd does not inherit the user's shell environment.  We try several
# sources in priority order to pick up optional API keys:
#
#   1. ~/.zshrc           — used for interactive shells on this machine
#   2. ~/.zprofile        — login-shell profile
#   3. ~/.zshenv          — always-sourced zsh env file
#   4. ~/.profile         — POSIX fallback
#   5. ~/.bash_profile    — bash login profile (sometimes shared)
#   6. ~/.secrets         — dedicated secrets file (recommended for launchd)
#   7. macOS Keychain     — via `security find-generic-password`
#
# source_scout.py uses Internet Archive as its default search backend
# (free, no key required).  For better general web coverage, optionally
# set BRAVE_API_KEY (free tier: 2,000 queries/month):
#
#   Get a free key at: https://api.search.brave.com
#
#   security add-generic-password -s BRAVE_API_KEY -a BRAVE_API_KEY -w your-key-here
# OR:
#   echo 'export BRAVE_API_KEY=your-key-here' >> ~/.secrets

source "$HOME/.zshrc"       2>/dev/null || true
source "$HOME/.zprofile"    2>/dev/null || true
source "$HOME/.zshenv"      2>/dev/null || true
source "$HOME/.profile"     2>/dev/null || true
source "$HOME/.bash_profile" 2>/dev/null || true
source "$HOME/.secrets"     2>/dev/null || true

# Keychain fallback for BRAVE_API_KEY
if [[ -z "$BRAVE_API_KEY" ]]; then
    _key="$(security find-generic-password -s BRAVE_API_KEY -w 2>/dev/null)"
    if [[ -n "$_key" ]]; then
        export BRAVE_API_KEY="$_key"
    fi
fi

exec python3 /Users/reify/Classified/goodcapital_landing/source_scout.py
