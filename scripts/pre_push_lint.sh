#!/usr/bin/env bash
# make lint and make mypy must both pass. pre-commit runs this on commit and on push.
set -u

cd "$(git rev-parse --show-toplevel)"

if [ -d venv-3.12.3/bin ]; then
    export PATH="$PWD/venv-3.12.3/bin:$PATH"
fi

status=0

echo "make lint"
make lint || status=1

echo "make mypy"
make mypy || status=1

exit "$status"
