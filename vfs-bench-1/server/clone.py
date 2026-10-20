import ctypes
import os
import shutil

# clonefile(2), where the C library has one: macOS, whose APFS shares a
# clone's blocks with its source until either of them is written.
CLONEFILE = getattr(ctypes.CDLL(None, use_errno=True), "clonefile", None)


def clone(src, dst):
    """Copy a file as `shutil.copy2` does, as a clone where the volume can.

    A run starts from a fresh copy of its fixture, and Atlas's fixture is the
    image's whole `/data`, 212 of its 250 MB the code executor's venv, copied
    again for every run and kept after it. A clone is the same bytes, mode
    and times for no space until one side is written, so a run sees exactly
    what the copy gave it, at 2 MB a workspace rather than 252. Anywhere
    `clonefile` cannot -- another volume, another OS, a destination that
    exists -- this is `copy2`.

    Args:
        src: the file.
        dst: where it goes.

    Returns:
        the destination, so `shutil.copytree` can take this as its
        `copy_function`.
    """
    if CLONEFILE is not None and CLONEFILE(os.fsencode(src), os.fsencode(dst),
                                           0) == 0:
        return dst
    return shutil.copy2(src, dst)
