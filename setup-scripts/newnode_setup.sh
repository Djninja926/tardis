#!/usr/bin/env bash
# newnode_setup.sh - bring up a fresh CloudLab C220G2 node to continue TARDIS work.
# Mirrors the ORIGINAL setup: clone sosp23-s3fifo, build libCacheSim, then clone the
# tardis-implementation fork in place of upstream cachelib-sosp23, disable turboboost,
# and build cachelib.
#
# Run on a fresh node AFTER: sudo chown -R $USER:$(id -gn) /mydata
# Match hardware to C220G2 (Wisconsin) so timing numbers stay comparable to banked results.

set -u
TARDIS=/mydata/tardis
ARTIFACT=https://github.com/Thesys-lab/sosp23-s3fifo.git
FORK=https://github.com/Djninja926/cachelib-sosp23.git
BRANCH=tardis-implementation
SCRIPTS_REPO=https://github.com/Djninja926/tempdata-repo.git
MSR_BASE="https://ftp.pdl.cmu.edu/pub/datasets/twemcacheWorkload/cacheDatasets/msr"

echo "############ 0. sanity ############"
if [ ! -w /mydata ]; then
  echo "ERROR: /mydata not writable. Run first:  sudo chown -R \$USER:\$(id -gn) /mydata"
  exit 1
fi
mkdir -p "$TARDIS/traces"

echo "############ 1. scripts + banked results repo ############"
cd "$TARDIS"
[ -d scratch-scripts ] || git clone "$SCRIPTS_REPO" scratch-scripts

echo "############ 2. clone the SOSP'23 artifact repo ############"
cd "$TARDIS"
[ -d sosp23-s3fifo ] || git clone "$ARTIFACT" sosp23-s3fifo
cd "$TARDIS/sosp23-s3fifo"

echo "############ 3. build libCacheSim (needed for data_gen.py etc.) ############"
pushd libCacheSim/scripts >/dev/null
bash install_dependency.sh
bash install_libcachesim.sh
popd >/dev/null

echo "############ 4. clone the TARDIS fork IN PLACE OF upstream cachelib-sosp23 ############"
cd "$TARDIS/sosp23-s3fifo"
if [ ! -d cachelib-sosp23 ]; then
  git clone "$FORK" cachelib-sosp23
fi
cd cachelib-sosp23
git checkout "$BRANCH"
git pull origin "$BRANCH" || git pull myfork "$BRANCH" || true
echo "code: $(git rev-parse --abbrev-ref HEAD) @ $(git rev-parse --short HEAD)"

echo "############ 5. turboboost OFF (critical for consistent throughput numbers) ############"
cd "$TARDIS/sosp23-s3fifo/cachelib-sosp23/mybench"
bash turboboost.sh disable

echo "############ 6. build cachelib (long: 30-60 min) ############"
bash build.sh

echo "--- binaries ---"
ls -1 "$TARDIS"/sosp23-s3fifo/cachelib-sosp23/mybench/_build/{lru,s3fifo,lruforgive} 2>/dev/null \
  || echo "WARNING: expected binaries missing. Check build.sh output before proceeding."

echo "############ 7. restore scripts + banked results ############"
cd "$TARDIS"
cp scratch-scripts/cache_size_sweep.sh scratch-scripts/plot_sweep.py "$TARDIS/traces/" 2>/dev/null
cp scratch-scripts/download_*.sh scratch-scripts/one_hit_ratio.py "$TARDIS/traces/" 2>/dev/null
cp scratch-scripts/sweep_results.csv "$TARDIS/sweep_results.csv" 2>/dev/null
cp scratch-scripts/sweep.log "$TARDIS/" 2>/dev/null
chmod +x "$TARDIS"/traces/*.sh 2>/dev/null
echo "restored $(wc -l < "$TARDIS/sweep_results.csv" 2>/dev/null || echo 0) banked result rows"

echo "############ 8. re-download traces needed GOING FORWARD ############"
echo "  Skipping metaKV (~70GB, no gap, banked) and the collapse-study wiki set."
echo "  Disk: 183G total. Watch it."
cd "$TARDIS/traces"

MSR_WANT="msr_proj_0 msr_proj_1 msr_proj_2 msr_proj_3 msr_proj_4 \
          msr_usr_0 msr_rsrch_0 msr_web_0 msr_mds_0 \
          msr_prxy_0 msr_src1_0 msr_hm_0 msr_prn_0"
for name in $MSR_WANT; do
  out="${name}.oracleGeneral"
  [ -f "$out" ] && { echo "have $out"; continue; }
  echo "GET $name"
  if wget -q --show-progress -O "$out.zst" "$MSR_BASE/$out.zst"; then
    zstd -d -q --rm "$out.zst" || rm -f "$out.zst"
  else
    echo "MISS $name"; rm -f "$out.zst"
  fi
done

echo ">>> Now fetch the non-MSR operating points (cache-t-00, cluster50, cluster53)."
echo ">>> download_traces.sh is the original: it may pull the FULL set incl. wiki_2019t"
echo ">>> and all 21 cache-t traces. Watch df -h /mydata and kill it if disk fills."
echo ">>> Run it manually:  bash /mydata/tardis/traces/download_traces.sh"

echo "############ 9. status ############"
echo "--- operating points (needed for MT phase + Bloom Stage 0) ---"
for t in msr_proj_0 cache-t-00 cluster53 cluster50; do
  [ -f "$TARDIS/traces/$t.oracleGeneral" ] && echo "  OK      $t" || echo "  MISSING $t  <-- fetch"
done
df -h /mydata | tail -1

cat <<'NEXT'

############ NEXT ############
1. Validate the restore (single most important check):
     cd /mydata/tardis/sosp23-s3fifo/cachelib-sosp23/mybench/_build
     ./lru /mydata/tardis/traces/msr_proj_0.oracleGeneral 256 24 1 1
   Expect miss ratio ~0.5062. If it matches, the environment is faithfully restored
   and every banked number stays valid.

2. Bloom filter Stage 0 (grounding check):
     python3 /mydata/tardis/traces/one_hit_ratio.py \
       /mydata/tardis/traces/msr_proj_0.oracleGeneral \
       /mydata/tardis/traces/cache-t-00.oracleGeneral
   Artifact alternative now available (libCacheSim is built):
     /mydata/tardis/sosp23-s3fifo/libCacheSim/scripts/plot_one_hit_trace.py

3. Resume the sweep (resumable, skips banked rows):
     cd /mydata/tardis/traces && nohup bash cache_size_sweep.sh > sweep2.log 2>&1 &

4. Operating points: msr_proj_0 @256MB, cache-t-00 @512MB (design doc Section 18.8).
NEXT
