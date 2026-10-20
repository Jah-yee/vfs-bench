#!/bin/sh
# Retain native kubectl semantics and record long-lived processes for the
# harness to close after the upstream grader. No task data lives here.
for arg in "$@"; do
    if [ "$arg" = port-forward ]; then
        printf '%s' "$$" > "$K8S_PROCESS_DIR/$$.pid"
        break
    fi
done
exec "$KUBECTL_NATIVE" --kubeconfig "$KUBECONFIG" "$@"
