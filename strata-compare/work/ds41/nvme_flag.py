#!/usr/bin/env python3
"""nvme_flag.py RUNDIR - 10-23 (the user): the model drive's temperature beside one DeepSeek run's results. Takes the rows of
logs/ds41/nvme-temp.tsv (work/ds41/nvmetemp.sh, every 30 s) inside the run's window (summary.txt's first and last
timestamps), writes them to RUNDIR/nvme-temp.tsv, and per request (ds41.jsonl: its end time, TTFT and decode time) the
hottest sample and the drive's alarm bit. A request is flagged when the drive went above 70 C (the user's line), its
alarm bit was set, or it reached 83 C (the drive's warning temperature, where its thermal throttling starts). Prints a
few lines for the summary; RUNDIR/nvme.txt has every request.
"""
import datetime as dt
import json
import re
import sys

LOG = "/home/USER/ai-speed-testing/strata-compare/logs/ds41/nvme-temp.tsv"
HOT, WARN = 70, 83
F = "%Y-%m-%d %H:%M:%S"


def main():
    d = sys.argv[1]
    stamps = re.findall(r"^=== (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)", open(f"{d}/summary.txt").read(), re.M)
    if not stamps:
        print("nvme0: no run window in summary.txt")
        return
    t0, t1 = dt.datetime.strptime(stamps[0], F), dt.datetime.strptime(stamps[-1], F) + dt.timedelta(seconds=30)
    rows = []
    for line in open(LOG):
        f = line.rstrip("\n").split("\t")
        if f[0] == "time":
            continue
        t = dt.datetime.strptime(f[0], F)
        if t0 <= t <= t1:
            rows.append((t, int(f[1]), int(f[2]), int(f[3]), f[4], int(f[5])))
    with open(f"{d}/nvme-temp.tsv", "w") as o:
        o.write("time\tcomposite_c\tsensor1_c\tsensor2_c\talarm\tread_MBps\n")
        for r in rows:
            o.write("\t".join([r[0].strftime(F)] + [str(x) for x in r[1:]]) + "\n")
    if not rows:
        print(f"nvme0: no temperature samples between {t0:%H:%M} and {t1:%H:%M} (the logger started 22:18)")
        return
    out, flagged = [], []
    try:
        recs = [json.loads(l) for l in open(f"{d}/ds41.jsonl")]
    except OSError:
        recs = []
    for r in recs:
        end = dt.datetime.strptime(r["t"], F)
        start = end - dt.timedelta(seconds=(r.get("ttft_s") or 0) + (r.get("decode_s") or 0) + 1)
        win = [x for x in rows if start <= x[0] <= end + dt.timedelta(seconds=30)]   # a sample covers the 30 s before it
        if not win:
            out.append(f"{r['id']} r{r['rep']}: no sample")
            continue
        mx, s1 = max(x[1] for x in win), max(x[2] for x in win)
        alarm = any(x[4] not in ("0", "-") for x in win)
        why = [w for w, c in ((f"> {HOT} C", mx > HOT), ("alarm bit", alarm), (f">= {WARN} C (throttle point)", mx >= WARN)) if c]
        out.append(f"{r['id']} r{r['rep']}: composite max {mx} C (sensor 1 {s1} C), read {min(x[5] for x in win)}-"
                   f"{max(x[5] for x in win)} MB/s{'  FLAGGED: ' + ', '.join(why) if why else ''}")
        if why:
            flagged.append(f"{r['id']} r{r['rep']} ({mx} C{', alarm' if alarm else ''})")
    open(f"{d}/nvme.txt", "w").write("\n".join(out) + "\n")
    mx = max(r[1] for r in rows)
    print(f"nvme0 (Samsung 9100 PRO): {len(rows)} samples {rows[0][0]:%H:%M}-{rows[-1][0]:%H:%M}, composite {min(r[1] for r in rows)}-{mx} C "
          f"(sensor 1 max {max(r[2] for r in rows)} C), alarm bit {'SET in ' + str(sum(r[4] not in ('0', '-') for r in rows)) + ' samples' if any(r[4] not in ('0', '-') for r in rows) else 'never set'}; "
          + (f"requests affected (> {HOT} C / alarm / >= {WARN} C): " + "; ".join(flagged) if flagged else f"no request above {HOT} C"))


if __name__ == "__main__":
    main()
