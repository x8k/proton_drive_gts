#!/usr/bin/env python3
"""Count unique multimedia files by content.

Unique-size files are counted by stat alone; only files that share
their size are hashed (Python 3.11+ for hashlib.file_digest).
Usage: python count_uniq.py [DIRECTORY]
"""

import collections
import hashlib
import os

from proton_drive_gts import SUPPORTED_EXTENSIONS


def digest(path):
    with open(path, "rb") as fh:
        return hashlib.file_digest(fh, "blake2b").hexdigest()


def main():
    target = os.sys.argv[1] if len(os.sys.argv) > 1 else "."

    sizes = collections.defaultdict(list)
    for root, _, files in os.walk(target):
        for name in files:
            if os.path.splitext(name)[1][1:].lower() in SUPPORTED_EXTENSIONS:
                path = os.path.join(root, name)
                try:
                    sizes[os.stat(path).st_size].append(path)
                except OSError:
                    pass

    uniq = 0
    for paths in sizes.values():
        uniq += 1 if len(paths) == 1 else len({digest(p) for p in paths})
    print(uniq)


if __name__ == "__main__":
    main()
