"""
Verify that every regulation in data/regulations.json still points at a live,
unchanged official source.

For each unique source_url it records the HTTP status, a SHA-256 hash of the
response body, and a UTC timestamp into data/source_status.json. On re-run it
compares against the previous hash and flags:

  OK         source reachable, content unchanged since last check
  CHANGED    source reachable but content hash differs -- review for amendments
  NEW        first time this source was checked
  MANUAL     live fetch blocked, but verified against a user-saved local copy
  UNREACHABLE  non-200 / network error AND no local copy on file

This is the "living" layer: a compliance team can trust the knowledge base only
if each cited source is shown to still exist and not have silently changed. It
fabricates nothing -- it only mirrors and hashes the public pages, or, when a
government server blocks automated requests, hashes a copy YOU saved from your
own browser.

Local-copy channel
------------------
Some official sites (e.g. Japan METI, NYC DCWP) block non-browser / data-centre
IPs, so an automated fetch from here returns UNREACHABLE even though the page is
fine in a normal browser. To get an honest, repeatable provenance trail for
those sources:

  1. Open the source_url in your own browser and Save As... the page (HTML or
     PDF) into data/source_copies/.
  2. Add an entry to data/source_copies/manifest.json mapping the source_url to
     the saved filename and the date you saved it:

        {
          "https://www.meti.go.jp/english/press/2024/0419_002.html": {
            "file": "meti-ai-guidelines.html",
            "saved_on": "2026-06-05",
            "note": "Saved from browser; gov server blocks automated requests."
          }
        }

  3. Re-run this script. For any URL that won't fetch live, it hashes your saved
     copy and records status MANUAL with that hash, so the source is still
     verifiable and you can diff the hash next time you re-download it.

The status is labelled MANUAL precisely so nobody mistakes a saved-copy check for
a live fetch -- it is honest about how each source was verified.
"""

import argparse
import datetime
import hashlib
import json
import os
import urllib.request

_HERE = os.path.dirname(__file__)
_REG_FILE = os.path.join(_HERE, "data", "regulations.json")
_STATUS_FILE = os.path.join(_HERE, "data", "source_status.json")
_COPIES_DIR = os.path.join(_HERE, "data", "source_copies")
_MANIFEST_FILE = os.path.join(_COPIES_DIR, "manifest.json")
_UA = "Mozilla/5.0 (cross-border-audit source-verifier; +https://github.com/zl1212-ship-it)"


def _fetch(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=40) as r:
        return r.status, r.read()


def _load_manifest() -> dict:
    """Map of source_url -> {file, saved_on, note} for user-saved local copies."""
    if not os.path.exists(_MANIFEST_FILE):
        return {}
    with open(_MANIFEST_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _local_copy_hash(entry: dict):
    """Return (sha256, abs_path) for a manifest entry, or (None, path) if absent."""
    path = os.path.join(_COPIES_DIR, entry["file"])
    if not os.path.exists(path):
        return None, path
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest(), path


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify cited regulation sources (live + local-copy fallback).")
    ap.add_argument("--list-missing", action="store_true",
                    help="List sources that are bot-blocked and have no local copy on file, then exit.")
    args = ap.parse_args()

    with open(_REG_FILE, encoding="utf-8") as f:
        reg = json.load(f)
    urls = sorted({o["source_url"] for o in reg["obligations"]})
    manifest = _load_manifest()

    previous = {}
    if os.path.exists(_STATUS_FILE):
        with open(_STATUS_FILE, encoding="utf-8") as f:
            previous = json.load(f).get("sources", {})

    sources = {}
    now = datetime.datetime.utcnow().isoformat() + "Z"
    missing_copies = []
    print(f"Verifying {len(urls)} official source(s)...\n")

    for url in urls:
        # 1) try a live fetch
        live_code = live_digest = live_err = None
        try:
            live_code, body = _fetch(url)
            if live_code == 200:
                live_digest = hashlib.sha256(body).hexdigest()
        except Exception as e:
            live_err = str(e)[:120]

        if live_digest is not None:
            # live fetch succeeded
            if url not in previous:
                state = "NEW"
            elif previous[url].get("sha256") != live_digest:
                state = "CHANGED"
            else:
                state = "OK"
            sources[url] = {"status": state, "http": live_code,
                            "sha256": live_digest, "checked_at": now,
                            "verified_via": "live fetch"}
        elif url in manifest:
            # live fetch blocked -- fall back to the user-saved local copy
            digest, path = _local_copy_hash(manifest[url])
            entry = manifest[url]
            if digest is not None:
                state = "MANUAL"
                prev_local = previous.get(url, {}).get("local_sha256")
                local_changed = prev_local is not None and prev_local != digest
                sources[url] = {
                    "status": "MANUAL", "http": live_code, "checked_at": now,
                    "verified_via": "saved local copy",
                    "local_file": entry["file"],
                    "local_sha256": digest,
                    "saved_on": entry.get("saved_on"),
                    "note": entry.get("note"),
                    "local_copy_changed_since_last_check": local_changed,
                    "live_fetch_error": live_err or f"HTTP {live_code}",
                }
            else:
                state = "UNREACHABLE"
                missing_copies.append(url)
                sources[url] = {"status": "UNREACHABLE", "http": live_code,
                                "error": f"manifest lists '{entry['file']}' but file not found at {path}",
                                "checked_at": now, "verified_via": "none"}
        else:
            state = "UNREACHABLE"
            missing_copies.append(url)
            sources[url] = {"status": "UNREACHABLE", "http": live_code,
                            "error": live_err or f"HTTP {live_code}",
                            "checked_at": now, "verified_via": "none"}

        tag = ""
        if sources[url].get("status") == "MANUAL":
            tag = f"  (saved copy {manifest[url].get('saved_on', '?')})"
        print(f"  [{sources[url]['status']:11}] {url}{tag}")

    if args.list_missing:
        print("\nSources that are bot-blocked AND have no local copy on file:")
        if not missing_copies:
            print("  (none -- every source is verified live or via a saved copy)")
        for u in missing_copies:
            print(f"  - {u}")
        print("\nTo verify one: save the page from your browser into data/source_copies/")
        print("and add it to data/source_copies/manifest.json (see the file's _how_to).")
        return

    with open(_STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump({"checked_at": now, "sources": sources}, f, indent=2)

    changed = [u for u, s in sources.items() if s["status"] == "CHANGED"]
    manual = [u for u, s in sources.items() if s["status"] == "MANUAL"]
    unreachable = [u for u, s in sources.items() if s["status"] == "UNREACHABLE"]
    print(f"\nWrote {_STATUS_FILE}")
    if changed:
        print(f"\n!! {len(changed)} source(s) CHANGED since last check -- review for amendments:")
        for u in changed:
            print(f"   {u}")
    if manual:
        print(f"\n   {len(manual)} source(s) verified from a saved local copy (live fetch blocked).")
    if unreachable:
        print(f"\n   {len(unreachable)} source(s) unreachable and with no local copy "
              f"-- run with --list-missing to see how to add one.")


if __name__ == "__main__":
    main()
