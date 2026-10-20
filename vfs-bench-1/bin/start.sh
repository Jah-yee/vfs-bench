#!/usr/bin/env bash
# The fixture stack, up and down and reset, as one command.
#
# Every fake both arms talk to runs in docker/compose.yml. What is *not* in
# there is the benchmark: mirage, the agent loop, the mirage CLIs and the
# evaluator all stay on the host, and reach the fakes on published loopback
# ports. So the container holds the fixtures and the host holds the
# measurement, which is the split that keeps `docker` out of the thing being
# measured.
#
#   bin/start.sh up               build the images, start the fakes, wait
#   bin/start.sh task <task>      that stack, ready for one task, from cold
#   bin/start.sh reset            empty every fake, seed nothing
#   bin/start.sh status           health, one line per service
#   bin/start.sh env              the exports the host side needs
#   bin/start.sh down             stop everything, keep the image
#
# `reset` empties every fake in the stack, not a chosen few: gws, github and
# GreenMail by the reset route they share, each notion workspace by name, the
# yfinance tables in place, and Cloud Logging's directory on the volume. It
# is a table plus a loop, so a fake added to compose is reset by adding a row
# rather than by remembering to write another curl.
#
# Nothing survives it, which is the point -- both arms run against the same
# services one after the other, and an arm that inherited the previous arm's
# writes would be graded on them.
#
# It was three container restarts until strukto-ai/mirage#905 gave the fakes
# a common reset route, and two of those restarts were emptying nothing:
# notion reopened the same SQLite every boot, and github's fixtures had to be
# smuggled in through a file because a restart could only replay the state it
# was launched with.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE="$REPO/docker/compose.yml"
export REPO_ROOT="$REPO"
export STACK_DIR="${STACK_DIR:-$REPO/state/stack}"
mkdir -p "$STACK_DIR"

compose() { docker compose -f "$COMPOSE" "$@"; }
gcp_compose() { docker compose -f "$COMPOSE" --profile gcp "$@"; }


status() {
    compose ps --format '  {{.Service}}\t{{.Status}}' 2>/dev/null |
        sort || true
}

endpoints() {
    cat <<EOF
export API_URL=http://127.0.0.1:${API_PORT:-9110}
export GWS_URL=http://127.0.0.1:${GWS_PORT:-19999}
export NOTION_URL=http://127.0.0.1:${NOTION_PORT:-5091}
export GITHUB_URL=http://127.0.0.1:${GITHUB_PORT:-19801}
export YF_DSN=postgresql://eigent:camel@localhost:${PG_PORT:-5433}/vfs_bench
export MAIL_IMAP_PORT=${MAIL_IMAP_PORT:-1143}
export MAIL_SMTP_PORT=${MAIL_SMTP_PORT:-1587}
export MAIL_API_PORT=${MAIL_API_PORT:-8081}
export BIGQUERY_EMULATOR_HOST=http://127.0.0.1:${BQ_PROXY_PORT:-9051}
export BQ_ENDPOINT=http://127.0.0.1:${BQ_PROXY_PORT:-9051}
export STORAGE_EMULATOR_HOST=http://127.0.0.1:${GCS_PORT:-9070}
export GCP_SERVICE_ACCOUNT=$STACK_DIR/gcp-service_account.keys.json
EOF
    # Projected from the fixture's own record rather than a second file
    # kept in step with it: what a task loaded is one fact, in one place.
    if [ -f "$STACK_DIR/fixture.json" ]; then
        python3 -c "import json,sys
loaded = json.load(open(sys.argv[1]))
if loaded.get('bigquery'):
    print(f\"export BQ_PROJECT='{loaded['bigquery']['project']}'\")
if loaded.get('seeded_at'):
    print(f\"export BQ_LAUNCH_TIME='{loaded['seeded_at']}'\")" \
            "$STACK_DIR/fixture.json"
    fi
}



# The workspaces the notion tasks declare, which is what `reset` has to
# empty. Read from the tasks rather than listed here, so a new notion task
# is reset by existing.


case "${1:-}" in
up)
    # stack.py builds the shared image and reconciles healthy containers too;
    # keeping that rule in the callable path also protects direct agent runs.
    uv run --project "$REPO" python "$REPO/server/fakes/stack.py" up
    echo
    endpoints
    ;;

# Everything one task needs, from nothing, in one command: the fakes up,
# every one of them emptied, BigQuery and Cloud Storage if the task asks
# for them, and the task's own fixtures rebuilt on top.
#
# The reset is not redundant with the rebuild. `server/seed/seed_task.py` restores
# what the task's manifest declares; what it cannot restore is a service
# the *previous* task seeded and this one does not mention, which stays up
# with the previous task's data in it. Emptying first is what makes the
# starting state a property of the task rather than of the run before it.
task)
    name="${2:-}"
    [ -z "$name" ] && {
        echo "usage: $(basename "$0") task <task>" >&2
        exit 2
    }
    [ -d "$REPO/task/toolathlon/$name" ] || {
        echo "no task directory at task/toolathlon/$name" >&2
        exit 2
    }

    # The seeder brings the stack up and empties it -- this verb is the
    # same thing with the ports exported into the caller's shell, which is
    # the one thing a Python process cannot do for it.
    eval "$(endpoints)"
    uv run --project "$REPO" python "$REPO/server/seed/seed_task.py" "$name"
    echo
    echo "ready: $name"
    endpoints
    ;;

reset) uv run --project "$REPO" python "$REPO/server/fakes/stack.py" reset ;;
status) status ;;
env) endpoints ;;

down)
    gcp_compose down --remove-orphans
    rm -f "$STACK_DIR/fixture.json"
    ;;

*)
    echo "usage: $(basename "$0") {up|task <task>|reset|status|env|down}" >&2
    exit 2
    ;;
esac
