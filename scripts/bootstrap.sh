#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
if [[ -f requirements-dev.txt ]]; then
  pip install -r requirements-dev.txt
fi
pip install -e .

echo "AURA development environment ready."
echo "Verify: aws sts get-caller-identity"
echo "Verify: terraform version"
