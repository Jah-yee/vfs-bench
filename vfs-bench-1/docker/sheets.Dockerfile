FROM node:24-bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends openssl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /opt/fixture/submodule/mirage/integ
ENV MIRAGE_BIND_HOST=0.0.0.0
COPY docker/package.json docker/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY integ ./
COPY server/fakes/research_gws.mjs /opt/fixture/server/fakes/research_gws.mjs
RUN INTEG_DB_URL=file:/tmp/generate.db ./node_modules/.bin/prisma generate --schema prisma/gws.prisma
ENTRYPOINT ["./node_modules/.bin/tsx", "/opt/fixture/server/fakes/research_gws.mjs", "--port", "19999"]
