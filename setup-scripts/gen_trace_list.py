#!/usr/bin/env python3
"""
gen_trace_list.py - build the master list of trace URLs for the all-traces sweep.

Scrapes the CMU twemcache dataset directory listing for the datasets we want,
emitting one .oracleGeneral.zst URL per line, each tagged with its dataset so
the partitioner can balance by dataset.

Output format (one per line):  <dataset>\t<url>

Datasets included (per Jane): cloudphysics, twitter (+ sample10 + sample100 as
separate folders), msr, fiu, systor, metaStorage, metaKV, metaCDN, wiki,
tencentPhoto, alibabaBlock/new (excluding 1K/1M/10K/100K subfolders),
tencentBlock/v2 (excluding size subfolders).

Usage:
  python3 gen_trace_list.py > master_trace_list.tsv
  python3 gen_trace_list.py --datasets msr,wiki > small_list.tsv   # subset for testing
"""
import sys, re, argparse, urllib.request

BASE = "https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets"

# dataset -> relative path under BASE. Some are nested; the size-subfolders
# (1K/1M/10K/100K) under alibabaBlock/new and tencentBlock/v2 are EXCLUDED by
# listing only the direct .zst files in those dirs (non-recursive).
DATASETS = {
    "cloudphysics":     "cloudphysics",
    "twitter":          "twitter",
    "twitter_sample10": "twitter/sample10",
    "twitter_sample100":"twitter/sample100",
    "msr":              "msr",
    "fiu":              "fiu",
    "systor":           "systor",
    "metaStorage":      "metaStorage",
    "metaKV":           "metaKV",
    "metaCDN":          "metaCDN",
    "wiki":             "wiki",
    "tencentPhoto":     "tencentPhoto",
    "alibabaBlock_new": "alibabaBlock/new",
    "tencentBlock_v2":  "tencentBlock/v2",
}

def list_dir(relpath):
    """Return oracleGeneral*.zst filenames directly in BASE/relpath (non-recursive).
    Matches variants: .oracleGeneral.zst, .oracleGeneral.bin.zst (cloudphysics),
    .oracleGeneral.sample10.zst / .sample100.zst (twitter samples), etc."""
    url = f"{BASE}/{relpath}/"
    try:
        html = urllib.request.urlopen(url, timeout=60).read().decode("utf-8", "replace")
    except Exception as e:
        print(f"# WARN: could not list {url}: {e}", file=sys.stderr)
        return []
    # any filename containing .oracleGeneral and ending in .zst (covers .bin.zst,
    # .sample10.zst, .sample100.zst, plain .oracleGeneral.zst).
    files = re.findall(r'href="([^"]*\.oracleGeneral[^"]*\.zst)"', html)
    files = [f for f in files if "/" not in f]  # direct files only, no nested paths
    return sorted(set(files))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", help="comma-separated subset of dataset keys (default: all)")
    ap.add_argument("--output", help="write list here as UTF-8 LF (avoids PowerShell UTF-16 redirect). Default: stdout")
    args = ap.parse_args()

    out = open(args.output, "w", encoding="utf-8", newline="\n") if args.output else sys.stdout
    keys = args.datasets.split(",") if args.datasets else list(DATASETS.keys())
    total = 0
    for key in keys:
        if key not in DATASETS:
            print(f"# WARN: unknown dataset '{key}', skipping", file=sys.stderr); continue
        relpath = DATASETS[key]
        files = list_dir(relpath)
        print(f"# {key}: {len(files)} traces", file=sys.stderr)
        for fn in files:
            out.write(f"{key}\t{BASE}/{relpath}/{fn}\n")
            total += 1
    if args.output:
        out.close()
    print(f"# TOTAL: {total} traces", file=sys.stderr)

if __name__ == "__main__":
    main()
