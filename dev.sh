#!/usr/bin/env bash
# Developer entry point for CloudCampusIQ (POSIX mirror of dev.ps1).
#
#   ./dev.sh            rebuild content, then serve on http://localhost:5000
#   ./dev.sh serve      same as above
#   ./dev.sh rebuild    rebuild the content database from content/*.yaml
#   ./dev.sh test       run the test suite
#   ./dev.sh check      rebuild + test + scan for banned strings
#   ./dev.sh install    install runtime and dev dependencies

set -euo pipefail

cd "$(dirname "$0")"

# Strings that must never reappear in the repo. The project was renamed away
# from an internal course code; this is what stops it creeping back in.
BANNED_STRINGS=("D324")

pick_python() {
    for candidate in .venv/bin/python venv/bin/python .venv/Scripts/python.exe venv/Scripts/python.exe; do
        [ -x "$candidate" ] && { echo "$candidate"; return; }
    done
    command -v python3 || command -v python
}

PYTHON="$(pick_python)"

do_rebuild() {
    echo "==> Rebuilding content database"
    "$PYTHON" -m flask --app app.py rebuild-content
}

do_test() {
    echo "==> Running tests"
    "$PYTHON" -m pytest -q
}

do_banned_scan() {
    echo "==> Scanning for banned strings"
    local failed=0
    for banned in "${BANNED_STRINGS[@]}"; do
        # .claude/ is excluded because the skill documents the rule and has to
        # be able to name the string it bans.
        if grep -rIn --fixed-strings \
            --exclude-dir=.git --exclude-dir=.claude --exclude-dir=__pycache__ \
            --exclude-dir=instance --exclude-dir=.venv --exclude-dir=venv \
            --exclude-dir=node_modules --exclude=dev.sh --exclude=dev.ps1 \
            "$banned" . ; then
            failed=1
        fi
    done
    [ "$failed" -eq 0 ] || { echo "found banned string reference(s)"; exit 1; }
    echo "    clean"
}

case "${1:-serve}" in
    install)
        echo "==> Installing dependencies"
        "$PYTHON" -m pip install -r requirements.txt
        "$PYTHON" -m pip install -r requirements-dev.txt
        ;;
    rebuild) do_rebuild ;;
    test)    do_test ;;
    check)
        do_rebuild
        do_test
        do_banned_scan
        echo "==> All checks passed"
        ;;
    serve)
        do_rebuild
        echo "==> Serving on http://localhost:5000  (Ctrl+C to stop)"
        "$PYTHON" app.py
        ;;
    *)
        echo "unknown command: $1" >&2
        exit 2
        ;;
esac
