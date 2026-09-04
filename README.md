# TARDIS / LRUForgive data directory

## Authoritative results
- results/final_sweep_perthread.csv        <- jane-perthread branch, full sweep
- results/final_sweep_single-manager.csv   <- tardis-implementation branch, full sweep

Sweep config: all 4 traces x 3 sizes, LRU+LruForgive at t=1/2/4/8/16,
S3FIFO+S3FIFOForgive at t=1 only (base S3-FIFO MT defect). Promote-to-main,
full fidelity (no subsampling), default hyperparameters. 3 reps.
LRU+S3FIFO baselines in the perthread file only (branch-independent, run once).
NA cells = cluster53 high-thread large-size (OOM/timeout); cluster53 is the
inverting trace, low-thread cells present, so these are non-blocking.

Headline: per-thread holds the full ~5.6pp LruForgive gap across 1-16 threads
(cache-t-00: ~0.772-0.776 flat), while single-manager degrades under load
(0.776 -> 0.809) as its single applier saturates. S3FIFOForgive: +0.7pp at t=1
on both branches.

## Layout
- results/            authoritative final sweeps (2 files)
- results/archive/    superseded/intermediate CSVs, provenance for design doc
- setup-scripts/      all scripts: env/trace setup, sweeps, reruns, plotting
- logs/              run logs and .out transcripts
- sosp23-s3fifo/     the CacheLib fork (code; branches tardis-implementation + jane-perthread)
- traces/            oracleGeneral traces (large, not uploaded anywhere)

## Key archive files (provenance)
- singlethread_sizesweep_all_traces.csv  <- the 21/26-trace single-thread validation (7.32% headline)
- s3fifoforgive_*                         <- S3FIFOForgive baselines + size sweep
- subsample_*                             <- subsampling investigation (note: _bugged_baseline is pre-encoding-fix)
- replicated_mode_matrix.csv / shared_mode_matrix.csv  <- mode comparison (shared mode retired)
- recency_window_sweep.csv / prxy1_cliff_sweep.csv / bimodality_sweep.csv  <- side investigations

Design doc (findings + full provenance): MultithreadedLRUForgive.md (Notion, manually maintained)
