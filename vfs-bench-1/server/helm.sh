#!/bin/bash
# Both tool surfaces use the same captured chart repository.
# helm reads Docker registry credentials from $HOME/.docker when it starts.
# The native sandbox denies the host's copy and upstream's image has none,
# so point it at an empty directory in helm's own config home.
if [[ -n "$HELM_CONFIG_HOME" ]]; then
  export DOCKER_CONFIG="$HELM_CONFIG_HOME/docker"
fi
args=()
for arg in "$@"; do
  if [[ "$arg" == 'https://charts.bitnami.com/bitnami' ]]; then
    arg="$HELM_FIXTURE_URL"
  fi
  args+=("$arg")
done
exec "$HELM_NATIVE" "${args[@]}"
