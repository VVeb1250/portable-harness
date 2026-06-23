#!/usr/bin/env bash
# Install the swebench scorer inside WSL (Linux python has `resource`; Windows
# native does not). Run once:  wsl -d Ubuntu bash /mnt/e/.../wsl_setup.sh
set -uo pipefail
echo "== wsl swebench setup =="
python3 --version
if docker ps >/dev/null 2>&1; then echo "docker_ok"; else echo "docker_FAIL (enable WSL integration in Docker Desktop)"; fi
python3 -c 'import resource; print("resource_ok")'
if python3 -c 'import swebench' 2>/dev/null; then
  echo "swebench already installed"
else
  echo "installing swebench (user site)..."
  python3 -m pip install --user --break-system-packages -q swebench \
    || python3 -m pip install --user -q swebench
fi
python3 -c 'import swebench; print("swebench_ready")'
