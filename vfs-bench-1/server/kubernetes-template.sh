set -eu
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iptables ca-certificates curl uidmap fuse3 openssh-server socat jq
curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-24.0.7.tgz -o /tmp/docker.tgz
tar -xzf /tmp/docker.tgz -C /tmp
cp /tmp/docker/* /usr/local/bin/
curl -fsSL https://kind.sigs.k8s.io/dl/v0.20.0/kind-linux-amd64 -o /usr/local/bin/kind
curl -fsSL https://dl.k8s.io/release/v1.27.3/bin/linux/amd64/kubectl -o /usr/local/bin/kubectl
chmod 755 /usr/local/bin/kind /usr/local/bin/kubectl
sha256sum /tmp/docker.tgz /usr/local/bin/kind /usr/local/bin/kubectl
docker --version
kind version
kubectl version --client --output=json
