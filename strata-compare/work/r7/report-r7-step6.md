### 5. C\*7 on 8080 and the 48-hour passive uptime monitor

04:09: `./switch-model.sh strata` started the promoted C\*7 on 127.0.0.1:8080 (engine `886b6ab2…` on both GPUs, SearXNG on
8888, a test question answered "51", "other apps use the Chat settings: temperature=1.0"). The **passive uptime
monitor** (`work/r7/uptime_monitor.py`, round 6's, paths in `logs/r7/uptime/`) runs for 48 hours. Every 15 minutes it
reads only `GET /health`, `/status` and `/metrics`, `/proc` and `nvidia-smi`, and never sends a model request or
restarts anything. It records your requests' timings (`requests.csv`), memory, file descriptors, idle CPU and free
VRAM (`samples.csv`), and every restart or identity change (`events.log`). First sample 04:09:37: healthy, MemAvailable
36.2 GiB, 5080 490 MiB free, 4060 Ti 1,052 MiB free. Stop it early with `kill $(cat logs/r7/uptime/monitor.pid)`.
