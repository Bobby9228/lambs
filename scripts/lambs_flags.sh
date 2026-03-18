#!/usr/bin/env bash
# Small helper to load and validate LAMBS feature flags.
# Usage:
#   source ./scripts/lambs_flags.sh
#   lambs_load_flags  # optional, auto-called when sourced
#
# Rules:
# - Accept only 0 or 1 for boolean flags.
# - Invalid values => warn to stderr, keep default.

set -euo pipefail

LAMBS_FLAGS_FILE_DEFAULT="${HOME}/.nanobot/workspace/.lambs_flags"

lambs_warn() {
  echo "[lambs_flags] WARN: $*" >&2
}

lambs_is_bool01() {
  [[ "$1" == "0" || "$1" == "1" ]]
}

lambs_load_flags() {
  local file="${LAMBS_FLAGS_FILE:-$LAMBS_FLAGS_FILE_DEFAULT}"
  if [[ -f "$file" ]]; then
    # shellcheck disable=SC1090
    source "$file"
  fi

  # Defaults
  : "${LAMBS_SEARCH_ENABLED:=1}"
  : "${LAMBS_WRITE_ENABLED:=1}"
  : "${LAMBS_CONSOLIDATE_ENABLED:=1}"
  : "${LAMBS_PATTERN_ENABLED:=1}"
  : "${LAMBS_SEMANTIC_ENABLED:=0}"

  for var in \
    LAMBS_SEARCH_ENABLED \
    LAMBS_WRITE_ENABLED \
    LAMBS_CONSOLIDATE_ENABLED \
    LAMBS_PATTERN_ENABLED \
    LAMBS_SEMANTIC_ENABLED
  do
    local val="${!var}" || true
    if ! lambs_is_bool01 "$val"; then
      lambs_warn "$var has invalid value '$val' (expected 0 or 1). Using default."
      case "$var" in
        LAMBS_SEMANTIC_ENABLED) export LAMBS_SEMANTIC_ENABLED=0 ;;
        *) export "$var"=1 ;;
      esac
    else
      export "$var"="$val"
    fi
  done
}

lambs_load_flags
