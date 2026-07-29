#!/usr/bin/env python3
"""
fiji_setup.py - locate a FIJI launcher, or download + install Fiji into the fishroi cache.

find_fiji()   -> path to an existing FIJI launcher (common install spots, cache, PATH) or None
install_fiji()-> download the platform Fiji from downloads.imagej.net/fiji/latest (sha256-verified),
                 extract into the cache (system unzip, to preserve perms/symlinks), return launcher
ensure_fiji() -> find_fiji() or install_fiji()

The launcher is the jaunch-style binary, e.g. macOS `Fiji.app/Contents/MacOS/fiji-macos-arm64`,
Linux `fiji-linux-x64`, Windows `fiji-windows-x64.exe`. Call it headless with
`<launcher> --headless --run script.py 'k="v",...'` (do NOT pass --console).

CLI: python fiji_setup.py            # prints a launcher path, installing Fiji if absent
"""
import glob, hashlib, os, platform, stat, subprocess, sys, urllib.request, zipfile

FIJI_BASE = "https://downloads.imagej.net/fiji/latest/"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_model import cache_dir


def _archive_name():
    s, m = platform.system(), platform.machine().lower()
    arm = m in ("arm64", "aarch64")
    if s == "Darwin":
        return "fiji-latest-macos-arm64-jdk.zip" if arm else "fiji-latest-macos64-jdk.zip"
    if s == "Linux":
        return "fiji-latest-linux-arm64-jdk.zip" if arm else "fiji-latest-linux64-jdk.zip"
    if s == "Windows":
        return "fiji-latest-win-arm64-jdk.zip" if arm else "fiji-latest-win64-jdk.zip"
    raise RuntimeError("unsupported platform for Fiji auto-install: %s/%s" % (s, m))


def _launcher_in(root):
    """Find a runnable fiji-* launcher under an install root (skip jaunch + hash sidecars)."""
    for pat in ("Contents/MacOS/fiji-*", "fiji-*",
                "Fiji.app/Contents/MacOS/fiji-*", "Fiji.app/fiji-*",
                "*/Contents/MacOS/fiji-*", "*/fiji-*"):
        for f in sorted(glob.glob(os.path.join(root, pat))):
            b = os.path.basename(f)
            if b.startswith("jaunch") or f.endswith((".md5", ".sha1", ".sha256", ".sha512")):
                continue
            if os.path.isfile(f):
                return f
    return None


def find_fiji(explicit=None):
    """Return an existing FIJI launcher path, or None."""
    if explicit and os.path.exists(explicit):
        return explicit
    roots = [os.path.join(cache_dir(), "Fiji"),
             "/Applications/Fiji/Fiji.app", "/Applications/Fiji.app",
             os.path.expanduser("~/Fiji.app"), os.path.expanduser("~/Applications/Fiji.app"),
             os.path.expanduser("~/Applications/Fiji/Fiji.app")]
    for r in roots:
        f = _launcher_in(r)
        if f:
            return f
    from shutil import which
    for name in ("fiji", "ImageJ-linux64", "ImageJ-macosx", "ImageJ-win64.exe"):
        w = which(name)
        if w:
            return w
    return None


def _sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _extract(zpath, dest):
    """Extract preserving unix perms/symlinks (system unzip on posix; zipfile on Windows)."""
    if os.name == "posix":
        subprocess.check_call(["unzip", "-q", "-o", zpath, "-d", dest])
    else:
        with zipfile.ZipFile(zpath) as z:
            z.extractall(dest)


def install_fiji(cache=None):
    """Download + install Fiji into the cache; return the launcher path."""
    root = os.path.join(cache or cache_dir(), "Fiji")
    os.makedirs(root, exist_ok=True)
    arch = _archive_name()
    url = FIJI_BASE + arch
    zpath = os.path.join(root, arch)

    print("downloading Fiji (~400 MB): %s" % url, file=sys.stderr)
    try:
        urllib.request.urlretrieve(url, zpath)
        want = urllib.request.urlopen(url + ".sha256", timeout=30).read().split()[0].decode()
    except Exception as ex:                                  # noqa: BLE001
        raise SystemExit(
            "could not download Fiji (%s).\n"
            "Install Fiji manually from https://fiji.sc/ and pass its launcher with --fiji." % ex)

    got = _sha256(zpath)
    if got != want:
        os.remove(zpath)
        raise SystemExit("Fiji sha256 mismatch: got %s, expected %s" % (got, want))

    print("extracting Fiji...", file=sys.stderr)
    _extract(zpath, root)
    os.remove(zpath)

    launcher = _launcher_in(root)
    if not launcher:
        raise SystemExit("Fiji extracted but no launcher found under %s" % root)
    os.chmod(launcher, os.stat(launcher).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return launcher


def ensure_fiji(explicit=None, cache=None):
    """Return a usable FIJI launcher: found if present, otherwise installed into the cache."""
    found = find_fiji(explicit)
    if found:
        return found
    print("FIJI not found; installing into the fishroi cache...", file=sys.stderr)
    return install_fiji(cache)


if __name__ == "__main__":
    print(ensure_fiji())
