#!/usr/bin/env python3
"""
partition_traces.py - split the master trace list into N balanced per-node shards.

Balances by trace COUNT across N nodes. Big datasets get split across nodes;
small datasets stay whole where possible. Every trace lands in exactly ONE
shard (no overlap), so results merge cleanly by trace name.

Input:  master_trace_list.tsv  (from gen_trace_list.py: <dataset>\t<url> per line)
Output: shard_00.txt .. shard_{N-1}.txt  (one URL per line, ready for the worker)

Usage:
  python3 partition_traces.py master_trace_list.tsv 12 --outdir shards/
"""
import sys, argparse, os
from collections import defaultdict

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master", help="master_trace_list.tsv")
    ap.add_argument("n_nodes", type=int)
    ap.add_argument("--outdir", default="shards")
    args = ap.parse_args()

    # read (dataset, url) rows, skip comments. utf-8-sig tolerates a UTF-8/UTF-16
    # BOM that PowerShell's > redirect adds.
    rows = []
    with open(args.master, encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            rows.append((parts[0], parts[1]))

    total = len(rows)
    N = args.n_nodes
    target = total / N
    print(f"{total} traces over {N} nodes, target {target:.1f}/node", file=sys.stderr)

    # group urls by dataset (keep order stable/sorted for determinism)
    by_ds = defaultdict(list)
    for ds, url in rows:
        by_ds[ds].append(url)
    for ds in by_ds:
        by_ds[ds].sort()

    # build "chunks": split any dataset larger than ~target into ceil(size/target)
    # contiguous pieces; keep smaller datasets whole. Then greedily pack chunks
    # into N bins by current load (Longest-Processing-Time heuristic).
    import math
    chunks = []  # (label, [urls])
    for ds, urls in sorted(by_ds.items(), key=lambda x: -len(x[1])):
        size = len(urls)
        if size > target * 1.3 and size > 1:
            k = max(1, round(size / target))
            base = size // k
            rem = size % k
            idx = 0
            for i in range(k):
                cnt = base + (1 if i < rem else 0)
                chunks.append((f"{ds}[{i+1}/{k}]", urls[idx:idx+cnt]))
                idx += cnt
        else:
            chunks.append((ds, urls))

    # LPT packing
    chunks.sort(key=lambda c: -len(c[1]))
    bins = [[] for _ in range(N)]
    loads = [0] * N
    assign = [[] for _ in range(N)]
    for label, urls in chunks:
        i = loads.index(min(loads))
        bins[i].extend(urls)
        loads[i] += len(urls)
        assign[i].append(f"{label}({len(urls)})")

    os.makedirs(args.outdir, exist_ok=True)
    for i in range(N):
        path = os.path.join(args.outdir, f"shard_{i:02d}.txt")
        with open(path, "w", newline="\n") as f:
            for url in bins[i]:
                f.write(url + "\n")
        print(f"  shard_{i:02d}: {loads[i]:>4} traces  {assign[i]}", file=sys.stderr)

    print(f"load range: {min(loads)}-{max(loads)} traces/node", file=sys.stderr)
    # sanity: no overlap, all accounted for
    written = sum(loads)
    assert written == total, f"MISMATCH: wrote {written} but had {total}"
    print(f"OK: all {total} traces assigned, no overlap", file=sys.stderr)

if __name__ == "__main__":
    main()
