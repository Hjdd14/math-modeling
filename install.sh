#!/usr/bin/env bash
#
# math-modeling skill installer
#
# Installs the Python dependencies used by the validation toolchain and runs a
# local health check ("doctor"). Run this script from the repository root after
# cloning, OR pipe it from the web via the one-line command shown in README.md.
#
# Usage:
#   ./install.sh                                 # install deps from current checkout
#   ./install.sh --skills-dir <path>             # also create a symlink to skills dir
#   ./install.sh --no-doctor                     # skip the doctor health check
#   SKILLS_DIR=~/.claude/skills ./install.sh     # set skills dir via env var
#
# Prerequisites (auto-checked by the script):
#   - git
#   - Python 3.10 or newer
#   - pip (usually ships with Python)

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SKILL_NAME="math-modeling"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Capture the inherited SKILLS_DIR env var BEFORE any later assignment clobbers it,
# so `SKILLS_DIR=... ./install.sh` keeps working as documented in the header.
SKILLS_DIR_ENV="${SKILLS_DIR:-}"

# ANSI helpers (only if stdout is a terminal, otherwise strip colors).
if [ -t 1 ]; then
    C_RESET=$'\033[0m'; C_RED=$'\033[31m'; C_GREEN=$'\033[32m'
    C_YELLOW=$'\033[33m'; C_BLUE=$'\033[34m'
else
    C_RESET=""; C_RED=""; C_GREEN=""; C_YELLOW=""; C_BLUE=""
fi
info()  { printf '%s[INFO]%s %s\n' "$C_BLUE"   "$C_RESET" "$*"; }
ok()    { printf '%s[ OK ]%s %s\n' "$C_GREEN"  "$C_RESET" "$*"; }
warn()  { printf '%s[WARN]%s %s\n' "$C_YELLOW" "$C_RESET" "$*"; }
die()   { printf '%s[ERR ]%s %s\n' "$C_RED"    "$C_RESET" "$*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
printf '%s================================%s\n' "$C_BLUE" "$C_RESET"
printf '%s  math-modeling skill installer%s\n'    "$C_BLUE" "$C_RESET"
printf '%s================================%s\n' "$C_BLUE" "$C_RESET"

# ---------------------------------------------------------------------------
# Preflight: detect git
# ---------------------------------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
    die "git not found. Install Git first: https://git-scm.com/downloads"
fi
info "Found $(git --version 2>&1)"

# ---------------------------------------------------------------------------
# Preflight: detect Python (prefer python3, fall back to python)
# ---------------------------------------------------------------------------
# Detect Python interpreter. Prefer python3, fall back to python.
# We must ACTUALLY EXECUTE the interpreter because Windows ships a
# python3 stub (%LOCALAPPDATA%\Microsoft\WindowsApps\python3.exe) that
# passes `command -v` but does not run Python — it opens the Microsoft
# Store instead. So we test the interpreter with a tiny `-c` command.
PY=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys' >/dev/null 2>&1; then
            PY="$candidate"
            break
        fi
    fi
done
if [ -z "$PY" ]; then
    die "Python not found. Install Python 3.10+ from https://www.python.org/downloads/"
fi

# Verify Python version >= 3.10 (capture stderr in case it prints warnings)
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    die "Python 3.10+ required. Current version: $("$PY" --version 2>&1)"
fi
info "Found $("$PY" --version 2>&1)"

# ---------------------------------------------------------------------------
# Locate skill source directory
# ---------------------------------------------------------------------------
if [ ! -f "$SCRIPT_DIR/SKILL.md" ]; then
    die "SKILL.md not found next to this script (expected at: $SCRIPT_DIR/SKILL.md)."
fi
if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
    die "requirements.txt not found next to this script (expected at: $SCRIPT_DIR/requirements.txt)."
fi
info "Skill source directory: $SCRIPT_DIR"

# ---------------------------------------------------------------------------
# Parse arguments
# ---------------------------------------------------------------------------
SKILLS_DIR_ARG=""
NO_DOCTOR=0
NO_PIP=0

while [ $# -gt 0 ]; do
    case "$1" in
        --skills-dir)
            shift
            [ $# -gt 0 ] || die "--skills-dir requires a path argument."
            SKILLS_DIR_ARG="$1"
            shift
            ;;
        --skills-dir=*)
            SKILLS_DIR_ARG="${1#*=}"
            shift
            ;;
        --no-doctor)
            NO_DOCTOR=1
            shift
            ;;
        --no-pip)
            NO_PIP=1
            shift
            ;;
        -h|--help)
            sed -n '2,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            die "Unknown option: $1 (use --help for usage)"
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Install Python dependencies
# ---------------------------------------------------------------------------
if [ "$NO_PIP" = "1" ]; then
    warn "Skipping pip install (--no-pip)."
else
    info "Installing Python dependencies from requirements.txt ..."
    ( cd "$SCRIPT_DIR" && $PY -m pip install -r requirements.txt ) \
        || die "pip install failed. See output above for details."
    ok "Python dependencies installed."
fi

# ---------------------------------------------------------------------------
# Optional: deploy symlink into agent skills directory
# ---------------------------------------------------------------------------
SKILLS_DIR=""
# 1. CLI argument takes highest priority
if [ -n "$SKILLS_DIR_ARG" ]; then
    SKILLS_DIR="$SKILLS_DIR_ARG"
fi
# 2. Environment variable (captured at the top of this script)
if [ -z "$SKILLS_DIR" ] && [ -n "$SKILLS_DIR_ENV" ]; then
    SKILLS_DIR="$SKILLS_DIR_ENV"
fi
# 3. Auto-detect common agent skills directories
if [ -z "$SKILLS_DIR" ]; then
    for candidate in "$HOME/.claude/skills" "$HOME/.config/opencode/skills"; do
        if [ -d "$(dirname "$candidate")" ]; then
            SKILLS_DIR="$candidate"
            break
        fi
    done
fi

if [ -n "$SKILLS_DIR" ]; then
    TARGET="$SKILLS_DIR/$SKILL_NAME"
    # Only symlink if the source path is NOT already the target (e.g. cloned directly there).
    if [ -d "$TARGET" ] && [ "$(cd "$TARGET" && pwd)" = "$(cd "$SCRIPT_DIR" && pwd)" ]; then
        ok "Skill source is already in the skills directory: $TARGET"
    elif [ -e "$TARGET" ] || [ -L "$TARGET" ]; then
        warn "An existing entry was found at $TARGET. Skipping symlink creation."
        warn "Remove it first if you want to (re)create the symlink."
    else
        info "Creating symlink: $TARGET -> $SCRIPT_DIR"
        if mkdir -p "$SKILLS_DIR" && ln -s "$SCRIPT_DIR" "$TARGET"; then
            ok "Symlink created. Your agent can now discover the skill at $TARGET."
        else
            warn "Symlink creation failed. You can manually copy or link the skill."
        fi
    fi
else
    info "No agent skills directory detected. If your agent uses one, re-run:"
    info "    $0 --skills-dir <path-to-your-skills-dir>"
fi

# ---------------------------------------------------------------------------
# Doctor health check
# ---------------------------------------------------------------------------
if [ "$NO_DOCTOR" = "1" ]; then
    warn "Skipping doctor health check (--no-doctor)."
elif [ -f "$SCRIPT_DIR/tools/doctor.py" ]; then
    info "Running doctor health check..."
    if ( cd "$SCRIPT_DIR" && $PY tools/doctor.py --workspace . ); then
        ok "Doctor check passed."
    else
        warn "Doctor reported warnings/issues. See output above for details."
        warn "The skill may still work; doctor output is informational."
    fi
else
    warn "Doctor script not found at $SCRIPT_DIR/tools/doctor.py; skipping."
fi

# ---------------------------------------------------------------------------
# Success
# ---------------------------------------------------------------------------
ok "Installation complete!"
cat <<EOF

Next steps:
  1. Restart your AI agent (Claude Code, OpenCode, or other) so it re-scans
     the skills directory.
  2. Trigger the skill by asking your agent to help with a math modeling
     problem (e.g. "帮我做一道数学建模题"), or by providing a problem file
     (PDF / DOCX / Markdown / TXT) together with any data attachments
     (Excel / CSV).

Skill location: $SCRIPT_DIR
Report bugs at: https://github.com/Hjdd14/math-modeling/issues
EOF