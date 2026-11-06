#!/usr/bin/env bash
# Runs on the server, called by the deploy job in .github/workflows/backend.yml:
#
#   echo <registry token> | bash /opt/voicemitra/remote-deploy.sh <git sha> <github user>
#
# Pulls that commit's image, restarts the API on it, and waits for /health/ready. If the new version
# doesn't come up, it goes back to the previous one and fails the job. Note: restarting the API drops
# any call in progress (live calls are kept in memory); reminders and dose timers are re-armed from the
# database at startup.
set -euo pipefail
cd /opt/voicemitra

TAG="${1:?usage: remote-deploy.sh <tag> <registry user>}"
REGISTRY_USER="${2:?usage: remote-deploy.sh <tag> <registry user>}"

[[ -f .env ]] || { echo "::error::/opt/voicemitra/.env is missing (deploy/README.md step 4)"; exit 1; }
# Without this file docker would create a *directory* in its place and Firebase would fail to load.
[[ -f secrets/firebase.json ]] || { echo "::error::/opt/voicemitra/secrets/firebase.json is missing (deploy/README.md step 4)"; exit 1; }

docker login ghcr.io -u "$REGISTRY_USER" --password-stdin >/dev/null
trap 'docker logout ghcr.io >/dev/null 2>&1 || true' EXIT

PREVIOUS="$(cat .deployed-tag 2>/dev/null || true)"

wait_ready() {
  for _ in $(seq 1 45); do
    if curl -fsS --max-time 3 http://127.0.0.1:8000/health/ready; then echo; return 0; fi
    sleep 2
  done
  return 1
}

echo "== deploying $TAG (previous: ${PREVIOUS:-none})"
IMAGE_TAG="$TAG" docker compose pull api
IMAGE_TAG="$TAG" docker compose up -d --remove-orphans

if wait_ready; then
  echo "$TAG" > .deployed-tag
  docker image prune -f >/dev/null
  echo "== $TAG is live"
  exit 0
fi

echo "::error::$TAG did not become ready; last log lines:"
docker compose logs --tail 60 api || true
if [[ -n "$PREVIOUS" ]]; then
  echo "== rolling back to $PREVIOUS"
  IMAGE_TAG="$PREVIOUS" docker compose up -d --remove-orphans
  wait_ready || echo "::error::the previous version $PREVIOUS is not ready either"
fi
exit 1
