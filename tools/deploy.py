# -*- coding: utf-8 -*-
"""Build the site and publish it on the web server.

    python tools/deploy.py --dry-run    # build and list what would be sent
    python tools/deploy.py              # build and publish

Where to publish is read from deploy.local.json at the repository root, which
is git-ignored so server details never reach the repository:

    {"host": "<ssh host>", "dir": "<folder the web server serves>"}

Needs only Python and an SSH key accepted by the server. The build goes into a
temporary folder, is sent as one archive over SSH, and replaces the content of
the remote folder in a single step.
"""
import argparse
import io
import json
import os
import shlex
import subprocess
import sys
import tarfile
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_pages  # noqa: E402

CONFIG = os.path.join(build_pages.ROOT, "deploy.local.json")
JUNK = {"desktop.ini", "Thumbs.db", ".DS_Store"}   # never published


def load_config():
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            cfg = json.load(fh)
        host, folder = cfg["host"], cfg["dir"]
    except (OSError, ValueError, KeyError):
        sys.exit(f"deploy: create {os.path.basename(CONFIG)} at the repository root:\n"
                 '  {"host": "<ssh host>", "dir": "<folder the web server serves>"}')
    if not folder.startswith("/") or folder.rstrip("/").count("/") < 2:
        sys.exit(f"deploy: refusing suspicious remote folder {folder!r}")
    return host, folder


def archive(folder):
    """tar.gz of the folder, readable by the web server whatever the local OS."""
    def normalise(info):
        if os.path.basename(info.name) in JUNK:
            return None
        info.uid = info.gid = 0
        info.uname = info.gname = ""
        info.mode = 0o755 if info.isdir() else 0o644
        return info

    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name in sorted(os.listdir(folder)):
            tar.add(os.path.join(folder, name), arcname=name, filter=normalise)
    return buf.getvalue()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="build and list, send nothing")
    args = ap.parse_args()
    host, folder = load_config()

    with tempfile.TemporaryDirectory() as tmp:
        site = os.path.join(tmp, "site")
        build_pages.build("production", site)
        data = archive(site)
        files = sum(1 for _, _, fs in os.walk(site) for f in fs if f not in JUNK)

    print(f"\n{files} files, {len(data) // 1024} KB compressed -> {host}:{folder}")
    if args.dry_run:
        print("dry run: nothing sent")
        return

    # cd first, under set -e: if the folder is missing, nothing gets deleted.
    remote = (f"set -e; cd {shlex.quote(folder)}; "
              "find . -mindepth 1 -delete; "
              "tar -xzf - --no-same-owner; "
              "echo published: $(find . -type f | wc -l) files")
    result = subprocess.run(["ssh", host, remote], input=data)
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
