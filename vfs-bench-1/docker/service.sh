#!/usr/bin/env bash
# One image, one service per invocation: `service.sh <name>`. compose runs
# six copies of this image with six different names, which is what makes
# `docker compose restart <name>` a per-service reset rather than a stack
# bounce.
#
# Every server binds 0.0.0.0 here. On the host these same programs bind the
# loopback, and that is still their default -- but a container that binds
# 127.0.0.1 publishes a port nothing answers on, which fails as a connection
# refused with no hint about why.
#
# One variable does it for all of them, which is what mirage's fakes read
# since strukto-ai/mirage#905. Before that each server was told separately
# and two of them ignored it: gws and notion took `--host` and dropped it on
# the floor, and github rejected the flag outright, so the stack came up with
# three services that accepted a connection and closed it with no response.
export MIRAGE_BIND_HOST=0.0.0.0
set -euo pipefail

INTEG=/opt/toolathlon/integ
SERVER=/opt/toolathlon/server
FIXTURE_DIR="${FIXTURE_DIR:-/fixtures}"

case "${1:-}" in
api)
    exec uvicorn app:app \
        --app-dir "$SERVER/api" \
        --host 0.0.0.0 --port "${API_PORT:-9110}" \
        --log-level warning
    ;;

gws)
    cd "$INTEG"
    exec ./node_modules/.bin/tsx server/gws/main.ts \
        --port "${GWS_PORT:-19999}" \
        --fixture-root "$FIXTURE_DIR/integ"
    ;;

notion)
    # This service's reset is *not* its restart. It never was -- the old
    # server reopened the same SQLite every boot, because it named the file
    # after a pid that is the same on every container start. Now it is not
    # even a file the container owns: the kit's ClientPool mkdtemp's a
    # directory per process and copies a `prisma db push` template into it
    # once per run, so INTEG_DB_URL is a build-time concern only and setting
    # it here would point at a database nothing opens.
    #
    # Resetting notion means `POST /reset` for one tenant, which is what
    # each notion task's seeder does through `server/clients/notion.py`.
    cd "$INTEG"
    exec ./node_modules/.bin/tsx server/notion/main.ts \
        --port "${NOTION_PORT:-5091}" \
        --fixture-root "$FIXTURE_DIR/integ" \
        --fixture empty
    ;;

github)
    # A kit fake now, not a Python process seeded from launch arguments, so
    # there is nothing left for `github.argv` to carry and restarting is no
    # longer the reset. The five tasks that used those arguments say the same
    # things through a fixture the host assembles under FIXTURE_DIR: a repo
    # row's `sourceDir` for a tree, `metaJson` for repository metadata,
    # `settings.createRepos` for what `--no-create-repos` meant, and the git
    # data API for the branches and commits a fixture cannot state.
    cd "$INTEG"
    exec ./node_modules/.bin/tsx server/github/main.ts \
        --port "${GITHUB_PORT:-19801}" \
        --fixture-root "$FIXTURE_DIR/integ" \
        --fixture empty
    ;;

bqproxy)
    exec python3 "$SERVER/bq/proxy.py" \
        --listen "${BQ_PROXY_PORT:-9051}" \
        --upstream "${BQ_UPSTREAM:-http://bigquery:9050}" \
        --storage "${GCS_URL:-http://gcs:4443}" \
        --bind 0.0.0.0
    ;;

tokenstub)
    # The key it writes lands in the shared volume because the readers are
    # on the host: both arms and the evaluator authenticate with it. Its
    # token_uri stays loopback on the *published* port, which is what a host
    # reader resolves -- `--port` is the container port the compose mapping
    # targets, and GCP_TOKEN_PORT only ever names the host side of it.
    # Writing the container port into the key is what made GCP_TOKEN_PORT
    # unmovable: on a second stack every `google_cloud_*` call spent the
    # whole 30-second budget on a port this stack does not answer on, and
    # where another checkout's stub held 9061 it authenticated against that
    # one's fixture and passed.
    project="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['bigquery']['project'])" \
        "$FIXTURE_DIR/fixture.json" 2>/dev/null || echo "")"
    exec python3 "$SERVER/bq/token_stub.py" \
        --port 9061 \
        --advertise "http://127.0.0.1:${GCP_TOKEN_PORT:-9061}" \
        --bind 0.0.0.0 \
        ${project:+--project "$project"} \
        --write-key "$FIXTURE_DIR/gcp-service_account.keys.json"
    ;;

hfhub)
    # Two ports, not one: the REST surface both arms' clients reach through
    # HF_ENDPOINT, and the MCP surface the MCP arm reaches instead of
    # huggingface.co/mcp. The tool document it publishes is a capture of the
    # real server, pinned under fixtures/hf-mcp/.
    cd "$INTEG"
    exec ./node_modules/.bin/tsx server/hf_hub/main.ts \
        --port "${HF_HUB_PORT:-5199}" \
        --mcp-port "${HF_MCP_PORT:-5200}" \
        --fixture-root "$FIXTURE_DIR/integ"
    ;;

*)
    echo "usage: service.sh {api|gws|notion|github|hfhub|bqproxy|tokenstub}" >&2
    exit 2
    ;;
esac
