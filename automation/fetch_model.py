#!/usr/bin/env python3
"""
fetch_model.py - download the FishROI 'rerio' Cellpose model to a local cache, md5-verified.

Only the universal 'rerio' model is fetched: the paper reports no statistically significant
benefit from the stage-specific (DR/J/pSB) models over 'rerio', so it is the single default.
The file is decoupled from the code (both fishroi_auto.py and fishroi_run_all.py take a local
model path), so this just stages that path once.

Cache: $FISHROI_CACHE, else $XDG_CACHE_HOME/fishroi, else ~/.cache/fishroi.

CLI:   python fetch_model.py            # prints the local model path (downloads if needed)
API:   from fetch_model import resolve_model
       path = resolve_model("auto")     # 'auto'/'rerio'/'' -> fetched rerio; else path as-is
"""
import argparse, hashlib, json, os, sys, urllib.request

ZENODO_RECORD = "19223252"
MODEL_KEY = "rerio_model"
FILES_API = "https://zenodo.org/api/records/%s/files" % ZENODO_RECORD
CONTENT_URL = "https://zenodo.org/api/records/%s/files/%s/content" % (ZENODO_RECORD, MODEL_KEY)
# Fallback hash if the Zenodo API is unreachable but the CDN is (belt and suspenders).
KNOWN_MD5 = "4753c0e041f55bf10409264a0fef2fef"


def cache_dir():
    base = os.environ.get("FISHROI_CACHE") or os.path.join(
        os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "fishroi")
    os.makedirs(base, exist_ok=True)
    return base


def _md5(path, chunk=1 << 20):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(chunk), b""):
            h.update(b)
    return h.hexdigest()


def _expected_md5():
    """Fetch the model's md5 from the Zenodo API; fall back to the pinned constant."""
    try:
        with urllib.request.urlopen(FILES_API, timeout=30) as r:
            data = json.load(r)
        for e in data.get("entries", []):
            if e.get("key") == MODEL_KEY:
                cs = e.get("checksum", "")
                return cs.split(":", 1)[1] if ":" in cs else cs
    except Exception as ex:                                   # noqa: BLE001
        print("warning: could not read Zenodo checksum (%s); using pinned md5" % ex,
              file=sys.stderr)
    return KNOWN_MD5


def get_rerio_model(dest_dir=None, expected_md5=None):
    """Return a local path to a verified rerio model, downloading to cache if needed."""
    dest_dir = dest_dir or cache_dir()
    path = os.path.join(dest_dir, MODEL_KEY)
    want = expected_md5 or _expected_md5()

    if os.path.exists(path) and want and _md5(path) == want:
        return path                                          # cached & valid

    tmp = path + ".part"
    print("fetching %s (26.6 MB) -> %s" % (MODEL_KEY, path), file=sys.stderr)
    try:
        urllib.request.urlretrieve(CONTENT_URL, tmp)
    except Exception as ex:                                  # noqa: BLE001
        raise SystemExit(
            "could not download the rerio model (%s).\n"
            "On an offline/locked-down node, download it manually from\n"
            "  https://doi.org/10.5281/zenodo.19223252  (file 'rerio_model')\n"
            "and pass its path with --model /path/to/rerio_model." % ex)

    got = _md5(tmp)
    if want and got != want:
        os.remove(tmp)
        raise SystemExit("md5 mismatch for %s: got %s, expected %s" % (MODEL_KEY, got, want))
    os.replace(tmp, path)
    return path


def resolve_model(spec, dest_dir=None):
    """'auto'/'rerio'/None/'' -> fetched rerio path; any other value -> returned unchanged."""
    if spec in (None, "", "auto", "rerio"):
        return get_rerio_model(dest_dir)
    return spec


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fetch the FishROI rerio Cellpose model")
    ap.add_argument("--cache-dir", default=None, help="override cache location")
    a = ap.parse_args()
    print(get_rerio_model(a.cache_dir))
