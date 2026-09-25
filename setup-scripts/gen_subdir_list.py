#!/usr/bin/env python3
"""
gen_subdir_list.py - scrape the subfolders that gen_trace_list.py deliberately skipped.

gen_trace_list.py keeps only the DIRECT .zst files in each dataset dir (the
`if "/" not in f` filter), so the size-subfolders under the block dirs were never
scraped. This walks one level down instead and emits them as their own datasets,
named <parent>_<subdir> (e.g. alibabaBlock_new_1K).

Output is the same dataset<TAB>url format as full_list.tsv, so you can just
concatenate the two and feed the result to remaining_traces.py / partition_traces.py.

Usage:
  python gen_subdir_list.py --out subdir_list.tsv
  python gen_subdir_list.py --parents alibabaBlock/new --out alibaba_subs.tsv
  python gen_subdir_list.py --list-only          # just show what subdirs exist, scrape nothing
"""
import sys, re, argparse, urllib.request

BASE = "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets"

# parent dirs whose subfolders we skipped the first time round
DEFAULT_PARENTS = [
    "alibabaBlock/new",
    "tencentBlock/v2",
]

# matches every variant: .oracleGeneral.zst, .oracleGeneral.bin.zst, .oracleGeneral.sample10.zst
TRACE_RE = re.compile(r'href="([^"]*\.oracleGeneral[^"]*\.zst)"')
DIR_RE = re.compile(r'href="([^"/]+)/"')


def fetch(url):
    try:
        return urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"# WARN: could not list {url}: {e}", file=sys.stderr)
        return ""


def subdirs_of(relpath):
    """Subdirectory names directly under BASE/relpath, excluding the parent link."""
    html = fetch(f"{BASE}/{relpath}/")
    names = [d for d in DIR_RE.findall(html) if not d.startswith("?")]
    # the Parent Directory anchor is an absolute path, so DIR_RE (no slashes allowed
    # in the name) already excludes it; dedupe and keep listing order stable
    seen, out = set(), []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def traces_in(relpath):
    """Direct .oracleGeneral*.zst files under BASE/relpath (non-recursive)."""
    html = fetch(f"{BASE}/{relpath}/")
    files = [f for f in TRACE_RE.findall(html) if "/" not in f]
    return sorted(set(files))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parents", help="comma-separated parent dirs (default: the two block dirs)")
    ap.add_argument("--out", default="subdir_list.tsv")
    ap.add_argument("--list-only", action="store_true",
                    help="print the subdirs and their trace counts, write nothing")
    args = ap.parse_args()

    parents = args.parents.split(",") if args.parents else DEFAULT_PARENTS

    rows, total = [], 0
    for parent in parents:
        subs = subdirs_of(parent)
        if not subs:
            print(f"# {parent}: no subdirectories found", file=sys.stderr)
            continue
        print(f"# {parent}: subdirs = {subs}", file=sys.stderr)
        for sub in subs:
            relpath = f"{parent}/{sub}"
            files = traces_in(relpath)
            ds = f"{parent.replace('/', '_')}_{sub}"
            print(f"#   {ds}: {len(files)} traces", file=sys.stderr)
            total += len(files)
            for fn in files:
                rows.append((ds, f"{BASE}/{relpath}/{fn}"))

    print(f"# TOTAL subdir traces: {total}", file=sys.stderr)

    if args.list_only:
        return

    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        for ds, url in rows:
            f.write(f"{ds}\t{url}\n")
    print(f"# wrote {len(rows)} rows -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
