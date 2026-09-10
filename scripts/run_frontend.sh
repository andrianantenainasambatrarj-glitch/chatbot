#!/usr/bin/env bash
# Lance le frontend React sur http://localhost:3000
set -euo pipefail
cd "$(dirname "$0")/../frontend"
[ -d node_modules ] || npm install
npm start
