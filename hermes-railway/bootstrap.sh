#!/command/with-contenv sh
set -eu

mkdir -p /opt/data/workspace/weather
chown -R hermes:hermes /opt/data/workspace

/command/s6-setuidgid hermes /bin/sh -c '
  set -eu
  export HOME=/opt/data
  /opt/hermes/.venv/bin/hermes config set model.provider openrouter
  /opt/hermes/.venv/bin/hermes config set model.default openrouter/free
  if [ ! -d /opt/data/workspace/weather/.git ]; then
    git clone --branch phase-1-backend-foundation --single-branch https://github.com/nonnolov/weather.git /opt/data/workspace/weather || true
  fi
'
