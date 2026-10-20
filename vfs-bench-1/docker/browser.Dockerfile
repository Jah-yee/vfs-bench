# The original npm lock selects Chromium and its entire server dependency tree.
FROM node:20-bookworm-slim@sha256:2cf067cfed83d5ea958367df9f966191a942351a2df77d6f0193e162b5febfc0
WORKDIR /opt/browser/vendor/browser-mcp
COPY vendor/browser-mcp/package.json vendor/browser-mcp/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && \
    node node_modules/playwright/cli.js install --with-deps chromium
COPY server/clients/browser.mjs /opt/browser/server/clients/browser.mjs
