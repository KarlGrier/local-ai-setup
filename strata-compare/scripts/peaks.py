"""Resource peaks from a monitor prefix: peak server RSS, min MemAvailable, swap, peak GPU memory, PCIe gen/width."""
import csv, sys
for prefix in sys.argv[1:]:
    rows = [r for r in csv.DictReader(open(prefix + ".sys.csv")) if r["pid"]]
    g = [l.strip().split(", ") for l in open(prefix + ".gpu.csv") if l.count(",") >= 5]
    gpu = [int(x[1]) for x in g if x[1].isdigit()]
    link = sorted({f"Gen{x[4]} x{x[5]}" for x in g})
    busy = [x for x in g if x[3].isdigit() and int(x[3]) > 30]
    link_busy = sorted({f"Gen{x[4]} x{x[5]}" for x in busy})
    print(f"{prefix}: samples {len(rows)}, peak server RSS {max(int(r['rss_mib']) for r in rows)} MiB, min MemAvailable "
          f"{min(int(r['memavail_mib']) for r in rows)} MiB, max swap used {max(int(r['swapused_mib']) for r in rows)} MiB, "
          f"peak GPU used {max(gpu)} MiB, PCIe seen {link}, PCIe while GPU>30% busy {link_busy}")
