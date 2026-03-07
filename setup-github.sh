#!/usr/bin/env bash
set -euo pipefail

REPO_NAME="fareradar"
DEFAULT_BRANCH="main"

REMOTE_URL="${1:-}"

echo "==> FareRadar GitHub setup starting..."

if [[ ! -d "frontend" || ! -d "backend" ]]; then
  echo "Error: run this script from the project root containing /frontend and /backend"
  exit 1
fi

echo "==> Writing .gitignore ..."
cat > .gitignore <<'EOG'
.env
.env.local
.env.production
frontend/.env
frontend/.env.local
backend/.env
backend/.env.local

node_modules/
.next/
out/
dist/
coverage/

__pycache__/
*.pyc
*.pyo
*.pyd
.venv/
venv/
env/

.DS_Store
.idea/
.vscode/
*.swp
EOG

echo "==> Checking required files ..."
REQUIRED_FILES=(
  "frontend/package.json"
  "frontend/vercel.json"
  "backend/requirements.txt"
  "backend/Procfile"
  "render.yaml"
  "schema.sql"
  "README.md"
)

MISSING=0
for file in "${REQUIRED_FILES[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file"
    MISSING=1
  fi
done

if [[ "$MISSING" -eq 1 ]]; then
  echo "Error: one or more required files are missing."
  exit 1
fi

echo "==> Initializing git repo if needed ..."
if [[ ! -d ".git" ]]; then
  git init
else
  echo "Git repo already initialized."
fi

echo "==> Setting default branch to ${DEFAULT_BRANCH} ..."
git branch -M "${DEFAULT_BRANCH}"

echo "==> Staging files ..."
git add .

if git diff --cached --quiet; then
  echo "No changes to commit."
else
  echo "==> Creating initial commit ..."
  git commit -m "Initial FareRadar deployment-ready build"
fi

if [[ -n "${REMOTE_URL}" ]]; then
  echo "==> Configuring remote origin ..."
  if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "${REMOTE_URL}"
  else
    git remote add origin "${REMOTE_URL}"
  fi

  echo "==> Pushing to GitHub ..."
  git push -u origin "${DEFAULT_BRANCH}"
else
  echo "==> No remote URL supplied."
  echo "To add it later, run:"
  echo "git remote add origin https://github.com/YOURUSERNAME/${REPO_NAME}.git"
  echo "git push -u origin ${DEFAULT_BRANCH}"
fi

echo
echo "FareRadar repo is ready."
echo
echo "Next steps:"
echo "1. Connect frontend/ to Vercel"
echo "2. Connect repo to Render using render.yaml"
echo "3. Add Supabase and Upstash env vars"
echo "4. Run schema.sql in Supabase"
