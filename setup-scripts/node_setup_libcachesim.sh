#!/usr/bin/env bash
# node_setup_libcachesim.sh - bring up a CloudLab node for the libCacheSim
# embedding sweep (Aryan's fork), replacing the CacheLib/mybench setup.
#
# Run AFTER:  sudo chown -R $USER:$(id -gn) /mydata
#
# Builds:  /mydata/cachesim/_build/bin/cachesim
# Does NOT download traces (the worker streams them one at a time).
#
# The old CacheLib tree at /mydata/tardis/sosp23-s3fifo is left alone unless
# PURGE_CACHELIB=1, so its results stay recoverable. Set PURGE_CACHELIB=1 only
# after you have collected node_out.csv off every node.
set -u

TARDIS=/mydata/tardis
LCS=/mydata/cachesim
LCS_REPO=https://github.com/Aryan470/libCacheSim.git
LCS_BRANCH=embeddings
SCRIPTS_REPO=https://github.com/Djninja926/tardis.git

echo "############ 0. sanity ############"
if [ ! -w /mydata ]; then
  echo "ERROR: /mydata not writable. Run:  sudo chown -R \$USER:\$(id -gn) /mydata"
  exit 1
fi
mkdir -p "$TARDIS/results"

# The worker needs wget + zstd only. numactl is not used: this is a miss-ratio
# sweep, and cachesim parallelizes internally across the algo x size grid.
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y wget zstd >/dev/null 2>&1 \
  && echo "wget + zstd ok" || echo "WARN: apt-get install wget zstd failed"

if [ "${PURGE_CACHELIB:-0}" = "1" ]; then
  echo "PURGE_CACHELIB=1 -> removing the old CacheLib tree to free disk"
  rm -rf "$TARDIS/sosp23-s3fifo"
else
  if [ -d "$TARDIS/sosp23-s3fifo" ]; then
    echo "NOTE: old CacheLib tree kept at $TARDIS/sosp23-s3fifo"
    echo "      ($(du -sh "$TARDIS/sosp23-s3fifo" 2>/dev/null | cut -f1) on disk; PURGE_CACHELIB=1 to remove)"
  fi
fi

echo "############ 1. scripts repo (worker + parser) ############"
cd "$TARDIS"
if [ -d scripts-repo ]; then
  (cd scripts-repo && git pull --ff-only origin main) || echo "WARN: scripts-repo pull failed"
else
  git clone "$SCRIPTS_REPO" scripts-repo || { echo "ERROR: scripts-repo clone failed"; exit 1; }
fi

echo "############ 2. clone Aryan's libCacheSim fork ($LCS_BRANCH) ############"
if [ -d "$LCS/.git" ]; then
  cd "$LCS"
  git fetch origin "$LCS_BRANCH" && git checkout "$LCS_BRANCH" && git pull --ff-only origin "$LCS_BRANCH"
else
  rm -rf "$LCS"
  git clone --branch "$LCS_BRANCH" "$LCS_REPO" "$LCS" || { echo "ERROR: clone failed"; exit 1; }
fi
cd "$LCS"
echo "code: $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)"

echo "############ 3. dependencies (cmake, ninja, glib, tcmalloc, zstd) ############"
bash scripts/install_dependency.sh 2>&1 | tail -5

echo "############ 4. build (cmake -G Ninja + ninja) ############"
bash scripts/install_libcachesim.sh 2>&1 | tee /tmp/lcs_build.log | tail -5

BIN="$LCS/_build/bin/cachesim"
if [ ! -x "$BIN" ]; then
  # the build script targets <repo>/_build, but don't guess if the layout moved
  FOUND=$(find "$LCS" -type f -name cachesim -perm -u+x 2>/dev/null | head -1)
  if [ -n "$FOUND" ]; then
    echo "NOTE: cachesim not at the expected path; found at $FOUND"
    BIN="$FOUND"
  else
    echo "ERROR: cachesim was not built. Last 30 lines of the build log:"
    tail -30 /tmp/lcs_build.log
    exit 1
  fi
fi

echo "############ 5. verify the two embedding policies are registered ############"
# cache_init.h maps these strings; if the binary lacks them the sweep would run
# but silently produce nothing for the policies we actually care about.
MISSING=0
for algo in lruforgiveembcache s3fifoforgive-embcache; do
  if strings "$BIN" | grep -qx "$algo"; then
    echo "  OK       $algo"
  else
    echo "  MISSING  $algo  <-- not registered in this build"
    MISSING=1
  fi
done
[ "$MISSING" = "1" ] && { echo "ERROR: expected policies missing; stopping."; exit 1; }

echo "############ done ############"
echo "cachesim: $BIN"
echo "$BIN" > "$TARDIS/cachesim_path.txt"
echo "Next:  bash $TARDIS/scripts-repo/setup-scripts/node_cachesim_worker.sh <shard> <out.csv>"
