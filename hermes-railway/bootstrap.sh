#!/command/with-contenv sh
set -eu

mkdir -p /opt/data/workspace/weather
chown -R hermes:hermes /opt/data/workspace

/command/s6-setuidgid hermes /bin/sh -c '
  set -eu
  export HOME=/opt/data

  /opt/hermes/.venv/bin/hermes config set model.provider openrouter
  /opt/hermes/.venv/bin/hermes config set model.default openrouter/free
  /opt/hermes/.venv/bin/hermes config set auxiliary.free_only true

  git config --global user.name Nutchanon
  git config --global user.email uojhfg@gmail.com

  if [ ! -d /opt/data/workspace/weather/.git ]; then
    if [ -n "${GH_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
      gh auth setup-git
      gh repo clone nonnolov/weather /opt/data/workspace/weather -- --branch phase-1-backend-foundation --single-branch
    elif [ -n "${GITHUB_TOKEN:-}" ] && command -v gh >/dev/null 2>&1; then
      export GH_TOKEN="$GITHUB_TOKEN"
      gh auth setup-git
      gh repo clone nonnolov/weather /opt/data/workspace/weather -- --branch phase-1-backend-foundation --single-branch
    else
      echo "[bootstrap] GitHub credential not configured; skipping private repo clone"
    fi
  fi
'
