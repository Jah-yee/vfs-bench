"""Install and verify the upstream Linux native-process sandbox."""
import hashlib
import io
import platform
import sys
import tarfile
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ENTRY = REPO / 'vendor/sandlock/sandlock'
# Upstream v0.8.8, commit 44ae89eed04b73a779f9b12d6e56de257c3bcc72.
# Archive hashes are GitHub release asset digests; binary hashes cover the
# extracted executable too, so a replaced local install fails before launch.
VERSION = '0.8.8'
RELEASES = {
    'aarch64':
    ('c93b184238c9d4f776548c0cff3003aa7c283fac0c91f652b816d34c72a04b10',
     '21a0bedd11c55f7837986a79390e0f379a3cba0b633299debbbadbbf2fd2856e'),
    'x86_64':
    ('ad9de854aa0a2607032bb6b50b84cb16967f8c2c20c6ae4468996338583625c6',
     'de0983fae7b4970ec8158565c37e0fee02783839c979928b170d8161ef2c0237'),
}


def release():
    arch = platform.machine()
    if arch not in RELEASES:
        raise RuntimeError(f'No pinned Sandlock release for Linux {arch}')
    return arch, RELEASES[arch]


def executable():
    """Verify the pin before every launch; never use an arbitrary PATH copy."""
    _, (_, expected) = release()
    if not ENTRY.is_file() or hashlib.sha256(
            ENTRY.read_bytes()).hexdigest() != expected:
        raise RuntimeError('Missing or changed pinned Linux sandbox; run '
                           '`uv run python -m server.linux_sandbox`')
    return str(ENTRY)


def main():
    if sys.platform != 'linux':
        print('Sandlock is only needed on Linux; macOS uses sandbox-exec')
        return 0
    arch, (archive_hash, binary_hash) = release()
    if ENTRY.is_file() and hashlib.sha256(
            ENTRY.read_bytes()).hexdigest() == binary_hash:
        return 0
    url = ('https://github.com/multikernel/sandlock/releases/download/'
           f'v{VERSION}/sandlock-{arch}-unknown-linux-gnu.tar.gz')
    with urllib.request.urlopen(url, timeout=120) as response:
        payload = response.read()
    if hashlib.sha256(payload).hexdigest() != archive_hash:
        raise RuntimeError('Sandlock release archive checksum mismatch')
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        member = archive.getmember('./sandlock')
        if not member.isfile():
            raise RuntimeError('Sandlock release executable is not a file')
        binary = archive.extractfile(member).read()
    if hashlib.sha256(binary).hexdigest() != binary_hash:
        raise RuntimeError('Sandlock executable checksum mismatch')
    ENTRY.parent.mkdir(parents=True, exist_ok=True)
    temporary = ENTRY.with_suffix('.tmp')
    temporary.write_bytes(binary)
    temporary.chmod(0o755)
    temporary.replace(ENTRY)
    print(f'Installed Sandlock {VERSION}: {ENTRY}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
