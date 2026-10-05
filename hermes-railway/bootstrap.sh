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
  /opt/hermes/.venv/bin/hermes config set auxiliary.openrouter_model nvidia/nemotron-3-ultra-550b-a55b:free

  git config --global user.name Nutchanon
  git config --global user.email uojhfg@gmail.com

  if [ ! -d /opt/data/workspace/weather/.git ]; then
    if [ -n "${GH_TOKEN:-}" ]; then
      git config --global credential.helper "!f() { echo username=x-access-token; echo password=\$GH_TOKEN; }; f"
      git clone --branch phase-1-backend-foundation --single-branch https://github.com/nonnolov/weather.git /opt/data/workspace/weather
    elif [ -n "${GITHUB_TOKEN:-}" ]; then
      export GH_TOKEN="$GITHUB_TOKEN"
      git config --global credential.helper "!f() { echo username=x-access-token; echo password=\$GH_TOKEN; }; f"
      git clone --branch phase-1-backend-foundation --single-branch https://github.com/nonnolov/weather.git /opt/data/workspace/weather
    else
      echo "[bootstrap] GitHub credential not configured; skipping private repo clone"
    fi
  fi
'
