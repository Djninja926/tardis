#!/usr/bin/env python3
"""
orchestrate.py - drive the multi-node all-traces sweep across CloudLab nodes.

Modeled on the Genet parallel-SSH pattern (paramiko + ThreadPoolExecutor).
For each node in parallel:
  1. (setup)  run node_setup.sh: clone repos, build libCacheSim + the fork
  2. (ship)   scp the node's shard list + the worker script
  3. (launch) start node_trace_worker.sh in a detached tmux session

Then use --collect to pull each node's result CSV back and merge.

Config: nodes.yaml
  username: ApiaO
  key_path: ~/.ssh/id_rsa            # optional; else uses agent/default
  repo: https://github.com/Djninja926/tardis.git
  nodes:
    - host: node0.cluster.cloudlab.us
    - host: node1.cluster.cloudlab.us
    ...

Usage:
  python3 orchestrate.py --config nodes.yaml --shards shards/ --setup     # phase 1: build on all nodes
  python3 orchestrate.py --config nodes.yaml --shards shards/ --launch    # phase 2: start workers
  python3 orchestrate.py --config nodes.yaml --status                     # check progress
  python3 orchestrate.py --config nodes.yaml --collect --outdir results/  # pull + merge CSVs
"""
import argparse, os, sys, time, concurrent.futures
import yaml
import paramiko

REMOTE_TARDIS = "/mydata/tardis"
REMOTE_SHARD  = f"{REMOTE_TARDIS}/shard.txt"
REMOTE_OUT    = f"{REMOTE_TARDIS}/results/node_out.csv"
WORKER        = f"{REMOTE_TARDIS}/scripts-repo/setup-scripts/node_trace_worker.sh"
SETUP         = f"{REMOTE_TARDIS}/scripts-repo/setup-scripts/node_setup.sh"
TMUX          = "tracesweep"

def connect(host, user, key_path):
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kw = {"username": user, "timeout": 30}
    if key_path:
        kw["key_filename"] = os.path.expanduser(key_path)
    c.connect(host, **kw)
    return c

def run(c, cmd, quiet=False):
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode(); err = stderr.read().decode()
    rc = stdout.channel.recv_exit_status()
    if not quiet:
        if out.strip(): print(out.strip())
        if err.strip(): print(err.strip(), file=sys.stderr)
    return rc, out, err

def do_setup(node, cfg):
    host = node["host"]; user = cfg["username"]; key = cfg.get("key_path")
    repo = cfg["repo"]
    print(f"[{host}] SETUP start")
    c = connect(host, user, key)
    try:
        # bootstrap: ensure /mydata writable, clone the scripts repo, run setup
        boot = (
            f"sudo chown -R $USER:$(id -gn) /mydata 2>/dev/null; "
            f"mkdir -p {REMOTE_TARDIS} && cd {REMOTE_TARDIS} && "
            f"([ -d scripts-repo ] || git clone {repo} scripts-repo) && "
            f"bash {SETUP}"
        )
        rc, _, _ = run(c, boot)
        print(f"[{host}] SETUP {'OK' if rc == 0 else 'FAILED rc='+str(rc)}")
        return rc == 0
    finally:
        c.close()

def do_launch(node, cfg, shard_path):
    host = node["host"]; user = cfg["username"]; key = cfg.get("key_path")
    print(f"[{host}] LAUNCH (shard {os.path.basename(shard_path)})")
    c = connect(host, user, key)
    try:
        # ship the shard list via SFTP
        sftp = c.open_sftp()
        run(c, f"mkdir -p {REMOTE_TARDIS}/results", quiet=True)
        sftp.put(shard_path, REMOTE_SHARD)
        sftp.close()
        # launch worker in a detached tmux session (survives disconnect)
        launch = (
            f"tmux kill-session -t {TMUX} 2>/dev/null; "
            f"tmux new-session -d -s {TMUX} "
            f"'bash {WORKER} {REMOTE_SHARD} {REMOTE_OUT} "
            f"> {REMOTE_TARDIS}/results/worker.log 2>&1'"
        )
        rc, _, _ = run(c, launch)
        print(f"[{host}] LAUNCH {'OK' if rc == 0 else 'FAILED'}")
        return rc == 0
    finally:
        c.close()

def do_status(node, cfg):
    host = node["host"]; user = cfg["username"]; key = cfg.get("key_path")
    c = connect(host, user, key)
    try:
        rc, out, _ = run(c,
            f"echo -n 'rows='; wc -l < {REMOTE_OUT} 2>/dev/null || echo 0; "
            f"echo -n 'tmux='; tmux has-session -t {TMUX} 2>/dev/null && echo RUNNING || echo DONE; "
            f"tail -1 {REMOTE_TARDIS}/results/worker.log 2>/dev/null",
            quiet=True)
        print(f"[{host}] {out.strip().replace(chr(10),' | ')}")
    finally:
        c.close()

def do_collect(node, cfg, outdir):
    host = node["host"]; user = cfg["username"]; key = cfg.get("key_path")
    c = connect(host, user, key)
    try:
        sftp = c.open_sftp()
        local = os.path.join(outdir, f"node_out_{host.split('.')[0]}.csv")
        try:
            sftp.get(REMOTE_OUT, local)
            print(f"[{host}] collected -> {local}")
        except FileNotFoundError:
            print(f"[{host}] no result CSV yet")
        sftp.close()
    finally:
        c.close()

def parallel(nodes, fn, *a):
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(nodes)) as ex:
        futs = {ex.submit(fn, nd, *a): nd["host"] for nd in nodes}
        for f in concurrent.futures.as_completed(futs):
            try: f.result()
            except Exception as e: print(f"[{futs[f]}] ERROR: {e}", file=sys.stderr)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--shards", help="dir with shard_NN.txt (for --launch)")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--launch", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--outdir", default="collected")
    args = ap.parse_args()

    cfg = yaml.safe_load(open(args.config))
    nodes = cfg["nodes"]

    if args.setup:
        parallel(nodes, do_setup, cfg)
    if args.launch:
        if not args.shards: sys.exit("--launch needs --shards")
        # pair node i with shard_i
        shards = sorted(f for f in os.listdir(args.shards) if f.startswith("shard_"))
        if len(shards) != len(nodes):
            print(f"WARN: {len(shards)} shards but {len(nodes)} nodes", file=sys.stderr)
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(nodes)) as ex:
            futs = {}
            for i, nd in enumerate(nodes):
                if i < len(shards):
                    sp = os.path.join(args.shards, shards[i])
                    futs[ex.submit(do_launch, nd, cfg, sp)] = nd["host"]
            for f in concurrent.futures.as_completed(futs):
                try: f.result()
                except Exception as e: print(f"[{futs[f]}] ERROR: {e}", file=sys.stderr)
    if args.status:
        parallel(nodes, do_status, cfg)
    if args.collect:
        os.makedirs(args.outdir, exist_ok=True)
        parallel(nodes, do_collect, cfg, args.outdir)
        # merge
        merged = os.path.join(args.outdir, "merged_all_nodes.csv")
        files = sorted(f for f in os.listdir(args.outdir) if f.startswith("node_out_"))
        with open(merged, "w") as out:
            hdr = False
            for fn in files:
                for j, line in enumerate(open(os.path.join(args.outdir, fn))):
                    if j == 0:
                        if not hdr: out.write(line); hdr = True
                        continue
                    out.write(line)
        print(f"merged {len(files)} node CSVs -> {merged}")

if __name__ == "__main__":
    main()
