# k8s-redis-helm-upgrade

Original Kind cluster and Redis 19.0.0 release in E2B. Native Helm upgrades
the same release using the supplied values. The original repository index
is frozen without changing the default chart version, and every Redis
archive it advertises -- 327 versions, 200 from `charts.bitnami.com` and 127
from the Docker Hub OCI registry -- is captured against the digest the index
names and served to both arms from the same loopback repository, so no
Redis entry reaches for Bitnami and none is hidden to make the catalog match
a smaller capture. The other 143 charts keep the URLs the index gives them;
the task names only Redis. Helm matches the upstream Dockerfile; its binary
checksum is verified.

Each measured arm owns a fresh sandbox through grading, then deletes it.
Prompts and fixtures come from the pinned Toolathlon checkout. DVC tracks
the captured artifacts and dependency sources; run records include image
digests and source hashes. No task-specific canned SQL responses are used.

After the usual repository setup, export `E2B_API_KEY` and install:

```sh
uv run python -m server.mcp.setup_kubernetes
uv run python -m server.mcp.setup_helm
uv run python server/kubernetes_template.py
```

Live integration (requires E2B credentials):

```sh
uv run python tests/kubernetes_extended.py KubernetesExtended.test_redis
```

The original grader has five checks: chart 22.0.0 deployed, custom values
preserved, pods running, service available and configuration correct.
