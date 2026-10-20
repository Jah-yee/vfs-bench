// Native command surface. Kubernetes data is owned by the API, not this CLI.
import { nativeCommand } from '../native.mjs'
export const KUBECTL = nativeCommand('kubectl', 'Operate on the Kubernetes cluster')
