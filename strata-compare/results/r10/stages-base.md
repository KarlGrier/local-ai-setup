| request | windows | avg T | tok/window | ms/window (host) | GPU stage total | draft round (host) | commit (host) | host waits for helper |
|---|---|---|---|---|---|---|---|---|
| warmup | 1 | 1.00 | 1.00 | 22.70 | 25.62 | 0.00 | 0.02 | 0 ms |
| math | 507 | 2.96 | 2.37 | 18.66 | 16.84 | 1.55 | 0.01 | 44 ms |
| code | 760 | 1.84 | 1.58 | 15.43 | 14.08 | 1.16 | 0.01 | 87 ms |
| ldr | 693 | 2.63 | 2.16 | 19.74 | 17.73 | 1.78 | 0.02 | 49 ms |
| math | 485 | 2.93 | 2.47 | 19.16 | 17.39 | 1.55 | 0.01 | 28 ms |
| code | 729 | 2.06 | 1.65 | 16.47 | 15.03 | 1.24 | 0.02 | 69 ms |
| ldr | 629 | 2.92 | 2.38 | 21.64 | 19.49 | 1.90 | 0.01 | 37 ms |

| stage (ms per window) | warmup | math | code | ldr |
|---|---|---|---|---|
| hyper-connection reads (mixer read measured, FFN read = same estimate) | 3.54 | 3.12 | 2.69 | 3.02 |
| router / ring / hits (hc-read1+router minus the FFN read; waitA = the pool's plan) | 0.71 | 0.68 | 0.68 | 0.71 |
| shared expert + expert inputs (shared+quant) | 0.96 | 0.94 | 0.86 | 0.93 |
| routed experts on the 5080 (VRAM hits) | 1.73 | 2.68 | 2.02 | 2.43 |
| PCIe call + its flag wait (empty at --pcie-frac 0) | 0.35 | 0.34 | 0.30 | 0.33 |
| wait for the CPU (waitCPU) | 10.36 | 3.44 | 2.54 | 4.75 |
| CPU rows + combine | 0.66 | 0.41 | 0.37 | 0.45 |
| GDN mixer (36 layers) | 3.45 | 2.97 | 2.71 | 2.95 |
| QSA mixer (12 layers) | 2.92 | 1.72 | 1.61 | 2.23 |
| head | 0.94 | 0.81 | 0.73 | 0.80 |
| gaps between layers | 0.03 | 0.03 | 0.03 | 0.03 |
| draft round (the MTP layer after the window, host clock) | 0.00 | 1.55 | 1.20 | 1.84 |
| commit + emit (host; the commit graph runs beside the draft) | 0.02 | 0.01 | 0.01 | 0.01 |
| **window, host clock** | **22.70** | **18.91** | **15.95** | **20.69** |
