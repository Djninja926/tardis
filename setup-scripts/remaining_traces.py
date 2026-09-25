#!/usr/bin/env python3
"""
remaining_traces.py - compute which traces still need running.

remaining = traces in the master list whose name does NOT yet appear with a
real (non-NA) miss value in the collected snapshot.

Output is the same dataset<TAB>url format as full_list.tsv, so partition_traces.py
accepts it unchanged (and still prints its per-dataset rollup). Use --bare if you
want plain URL-per-line instead.

Usage:
  python remaining_traces.py full_list.tsv maindata_snapshot\\merged_all_nodes.csv --out remaining.tsv --reverse
"""
import sys, csv, argparse


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("master")                 # full_list.tsv: dataset<TAB>url
    ap.add_argument("done_csv")               # merged snapshot
    ap.add_argument("--out", default="remaining.tsv")
    ap.add_argument("--bare", action="store_true",
                    help="write bare URLs instead of dataset<TAB>url")
    ap.add_argument("--reverse", action="store_true",
                    help="emit remaining traces in reverse master order, so free nodes "
                         "work backward while the still-running nodes work forward "
                         "(meet in the middle, minimizes duplicate work)")
    ap.add_argument("--require-both-sizes", action="store_true",
                    help="only count a trace done if it has real rows at BOTH cache_pct 10 and 0.1. "
                         "Leave OFF normally: huge 10%% cells are legitimately NA_TOOBIG.")
    args = ap.parse_args()

    # trace -> set of cache_pct values that have at least one real (non-NA) miss
    done_pcts = {}
    with open(args.done_csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            miss = (r.get("miss") or "").strip()
            if miss and not miss.startswith("NA"):
                done_pcts.setdefault(r["trace"], set()).add((r.get("cache_pct") or "").strip())

    def is_done(tr):
        pcts = done_pcts.get(tr, set())
        if not pcts:
            return False
        if args.require_both_sizes:
            return ("10" in pcts) and ("0.1" in pcts)
        return True

    rows, total, per_ds = [], 0, {}
    with open(args.master, encoding="utf-8-sig") as f:
        for line in f:
            line = line.rstrip("\n").rstrip("\r")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) != 2:
                continue
            ds, url = parts[0].strip(), parts[1].strip()
            name = url.rsplit("/", 1)[-1].split(".oracleGeneral")[0]
            total += 1
            if not is_done(name):
                rows.append((ds, url))
                per_ds[ds] = per_ds.get(ds, 0) + 1

    if args.reverse:
        rows.reverse()

    with open(args.out, "w", encoding="utf-8", newline="\n") as out:
        for ds, url in rows:
            out.write(url + "\n" if args.bare else f"{ds}\t{url}\n")

    for ds, n in sorted(per_ds.items(), key=lambda kv: -kv[1]):
        print(f"# {ds}: {n} remaining", file=sys.stderr)
    print(f"# master={total}  done={total - len(rows)}  REMAINING={len(rows)} -> {args.out}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
