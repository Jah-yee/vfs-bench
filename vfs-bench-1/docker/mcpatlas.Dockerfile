# Upstream's own sandbox, and what it fetches at every start rather than
# carrying: the four servers it runs from a GitHub branch, at the commit each
# branch held when the image was built, and readabilipy's JavaScript, which
# the fetch server installs on its first page. Nothing the image carries is
# touched -- /data, /root and every server it installs stay upstream's.
FROM ghcr.io/scaleapi/mcp-atlas:1.2.7@sha256:24e6ed3534916afe2c6825382da159a30e23516ef612be5d074fd96a74f9184c

WORKDIR /opt/vfs-bench
COPY vendor/mcpatlas-mcp/github/package.json vendor/mcpatlas-mcp/github/package-lock.json github/
COPY vendor/mcpatlas-mcp/weather/package.json vendor/mcpatlas-mcp/weather/package-lock.json weather/
RUN cd github && npm ci --no-audit --no-fund && cd ../weather && npm ci --no-audit --no-fund

COPY vendor/mcpatlas-mcp/pubmed/pyproject.toml vendor/mcpatlas-mcp/pubmed/uv.lock pubmed/
COPY vendor/mcpatlas-mcp/weather-data/pyproject.toml vendor/mcpatlas-mcp/weather-data/uv.lock weather-data/
RUN cd pubmed && uv sync --frozen && cd ../weather-data && uv sync --frozen

COPY vendor/mcpatlas-mcp/fetch/readabilipy/package-lock.json /root/.local/share/uv/tools/mcp-server-fetch/lib/python3.12/site-packages/readabilipy/javascript/
RUN cd /root/.local/share/uv/tools/mcp-server-fetch/lib/python3.12/site-packages/readabilipy/javascript && npm ci --no-audit --no-fund

WORKDIR /agent-environment
