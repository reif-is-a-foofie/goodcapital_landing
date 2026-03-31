#!/bin/zsh
# Wrapper for source_scout.py run via launchd.
# launchd does not inherit the user's shell environment, so we source
# ~/.zprofile here to pick up PATH, ANTHROPIC_API_KEY, and other exports
# that are set in the login profile.

source "$HOME/.zprofile" 2>/dev/null || true

exec python3 /Users/reify/Classified/goodcapital_landing/source_scout.py
