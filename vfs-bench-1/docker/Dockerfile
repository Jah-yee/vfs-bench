# One image, six services. Each fixture service is the same image with a
# different command, which is what makes `docker compose restart <service>`
# the reset: every fake in here holds its state in memory or in a SQLite
# file `prisma db push` recreates on start, so restarting the process is
# restoring the fixture. Nothing is persisted on purpose.
#
# The four services *not* built here -- BigQuery, Cloud Storage, GreenMail,
# Postgres -- are upstream images pinned in compose.yml, because a fake we
# did not write should be pulled rather than rebuilt.
FROM node:20-bookworm-slim

# python3.11 is what bookworm ships and all four Python services run on it:
# they use pathlib, contextvars and collections.abc and nothing newer. The
# benchmark's own venv is 3.12 and stays on the host -- this is the fixture
# side of the wire, not the agent side.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-venv curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
# Pinned: an unpinned fixture dependency is the same defect as an unpinned
# MCP server -- the surface moves under a measurement that claims it did not.
RUN pip install --no-cache-dir \
        "fastapi==0.115.6" \
        "uvicorn==0.34.0" \
        "cryptography==44.0.0" \
        "aiohttp==3.11.11"

# node_modules sits at the integ root because the kit resolves the prisma CLI
# with createRequire(import.meta.url), which walks up from
# integ/server/kit/typescript/db.ts.
WORKDIR /opt/toolathlon/integ
COPY docker/package.json ./package.json
RUN npm install --omit=dev --no-audit --no-fund

# The kit derives every one of its own paths from its file location --
# `fixture.ts` sets INTEG_ROOT to `resolve(HERE, '..', '..', '..')` and hangs
# FIXTURE_ROOT and SCHEMA_ROOT off it -- so this tree has to be shaped like
# mirage's own integ/, not flattened. `server/kit` is copied because both
# fakes import it; notion is a kit fake outright and gws borrows its Router,
# tenant and reset.
COPY submodule/mirage/integ/server/kit ./server/kit
COPY submodule/mirage/integ/server/gws ./server/gws
COPY submodule/mirage/integ/server/notion ./server/notion
COPY submodule/mirage/integ/server/github ./server/github
COPY submodule/mirage/integ/server/hf_hub ./server/hf_hub
COPY submodule/mirage/integ/prisma ./prisma
COPY submodule/mirage/integ/fixtures/notion ./fixtures/notion
COPY submodule/mirage/integ/fixtures/github ./fixtures/github
# hf-mcp/tools.json is the captured huggingface.co/mcp tool
# document the MCP arm is served. It is upstream's bytes, not
# ours, which is the only reason a local MCP server can stand in
# for the remote one without changing what the model is sent.
COPY submodule/mirage/integ/fixtures/hf-hub ./fixtures/hf-hub
COPY submodule/mirage/integ/fixtures/hf-mcp ./fixtures/hf-mcp

# One schema per service, each declaring its own
# `output = "../generated/<service>"` which the fake imports by that path.
# Three now rather than one: github stopped being a Python process and gws
# stopped being in-memory, so both have a client of their own -- mirage's
# `prisma:clients` script now runs `generate` over every schema and
# `validate` over none.
# INTEG_DB_URL is set because the datasource reads it through env() and
# `generate` refuses a schema it cannot resolve -- the value is never
# connected to, and at run time the kit's ClientPool passes each run's file
# as `datasourceUrl` instead.
RUN for schema in notion gws github hf_hub; do \
        INTEG_DB_URL=file:/tmp/generate.db \
            ./node_modules/.bin/prisma generate \
            --schema "./prisma/$schema.prisma" || exit 1; \
    done

COPY server/api /opt/toolathlon/server/api
COPY server/bq /opt/toolathlon/server/bq
COPY docker/service.sh /usr/local/bin/service.sh
RUN chmod +x /usr/local/bin/service.sh

# Written by the host before it restarts a service, read by the service as
# it comes up: a per-task fixture pointer that survives `docker restart`
# where an environment variable would need the container recreated.
VOLUME /fixtures
ENV FIXTURE_DIR=/fixtures

WORKDIR /opt/toolathlon
ENTRYPOINT ["/usr/local/bin/service.sh"]
