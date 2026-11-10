### helper 3300 slots
requests parsed: 15

| # | prompt | reused | generated | windows | avg T | tok/window | ms/window | GPU stage total | draft | helper wait ms |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 9657 | 0 | 1 | 1 | 1.00 | 1.00 | 21.30 | 22.87 | 0.00 | 0 |
| 1 | 180 | 0 | 257 | 119 | 2.88 | 2.16 | 18.07 | 16.57 | 1.35 | 41 |
| 2 | 19372 | 0 | 8192 | 3698 | 2.70 | 2.22 | 16.77 | 15.16 | 1.49 | 2080 |
| 3 | 171 | 0 | 194 | 88 | 2.84 | 2.20 | 18.94 | 17.57 | 1.41 | 26 |
| 4 | 8153 | 0 | 4096 | 1804 | 2.77 | 2.27 | 16.80 | 15.25 | 1.43 | 955 |
| 5 | 2578 | 0 | 2048 | 996 | 2.48 | 2.06 | 15.93 | 14.53 | 1.29 | 653 |
| 6 | 21834 | 0 | 8192 | 3337 | 2.99 | 2.45 | 17.12 | 15.38 | 1.62 | 2315 |
| 7 | 21809 | 16384 | 4096 | 1628 | 3.01 | 2.52 | 16.77 | 15.06 | 1.61 | 1249 |
| 8 | 2513 | 0 | 2048 | 964 | 2.61 | 2.12 | 16.24 | 14.80 | 1.33 | 746 |
| 9 | 4810 | 0 | 4096 | 1949 | 2.68 | 2.10 | 16.35 | 14.85 | 1.38 | 1321 |
| 10 | 3066 | 0 | 263 | 126 | 2.90 | 2.09 | 18.47 | 17.00 | 1.44 | 52 |
| 11 | 13064 | 0 | 4096 | 1712 | 3.07 | 2.39 | 17.49 | 15.81 | 1.56 | 843 |
| 12 | 35908 | 0 | 8192 | 3503 | 2.84 | 2.34 | 17.23 | 15.49 | 1.62 | 2381 |
| 13 | 137 | 0 | 4096 | 1748 | 2.80 | 2.34 | 15.34 | 13.86 | 1.37 | 1301 |
| 14 | 151 | 0 | 4096 | 2306 | 2.23 | 1.78 | 14.26 | 12.95 | 1.20 | 2350 |

### Stage table (GPU stamps, ms per window; pooled over each group's windows)

| stage | ldr | math | code |
|---|---|---|---|
| hyper-connection reads (both; FFN read = the mixer read's time) | 2.50 | 2.50 | 2.40 |
| router / ring / hits | 0.51 | 0.49 | 0.49 |
| plan wait (waitA) | 0.28 | 0.26 | 0.26 |
| shared expert + expert inputs | 0.83 | 0.82 | 0.78 |
| routed experts on the 5080 (VRAM hits) | 2.30 | 2.46 | 2.04 |
| PCIe stage (empty) | 0.27 | 0.27 | 0.26 |
| **wait for the CPU (waitCPU)** | 3.64 | 2.35 | 2.13 |
| CPU rows + combine | 0.46 | 0.43 | 0.42 |
| GDN mixer (36 layers) | 2.39 | 2.38 | 2.34 |
| QSA mixer (12 layers) | 1.43 | 1.23 | 1.15 |
| head | 0.65 | 0.65 | 0.63 |
| gaps | 0.03 | 0.03 | 0.03 |
| GPU stage total | 15.26 | 13.86 | 12.95 |
| draft round (host) | 1.52 | 1.37 | 1.20 |
| commit + emit (host) | 0.01 | 0.01 | 0.01 |
| **window, host clock** | 16.89 | 15.34 | 14.26 |
| tokens per window | 2.30 | 2.34 | 1.78 |

### The CPU path, ms per window (summed over the 48 layers; pooled)

| part | ldr | math | code |
|---|---|---|---|
| reach | 7.569 | 7.612 | 7.268 |
| host | 7.028 | 5.584 | 5.026 |
| plan | 0.499 | 0.466 | 0.454 |
| helper-begin | 0.446 | 0.416 | 0.415 |
| actq | 0.000 | 0.000 | 0.000 |
| jobs | 0.054 | 0.038 | 0.036 |
| pool | 5.741 | 4.255 | 3.434 |
| gu | 3.431 | 2.530 | 2.051 |
| midq | 0.038 | 0.028 | 0.023 |
| down | 2.246 | 1.673 | 1.339 |
| park | 0.014 | 0.013 | 0.011 |
| helper-finish | 0.706 | 0.798 | 1.073 |
| waitA | 0.273 | 0.267 | 0.264 |
| waitCPU | 3.635 | 2.337 | 2.119 |
### helper 2400 slots
requests parsed: 15

| # | prompt | reused | generated | windows | avg T | tok/window | ms/window | GPU stage total | draft | helper wait ms |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 9657 | 0 | 1 | 1 | 1.00 | 1.00 | 21.24 | 24.55 | 0.00 | 0 |
| 1 | 180 | 0 | 370 | 155 | 2.97 | 2.39 | 19.27 | 17.74 | 1.40 | 31 |
| 2 | 19372 | 0 | 8192 | 3756 | 2.67 | 2.18 | 17.38 | 15.78 | 1.48 | 1164 |
| 3 | 171 | 0 | 264 | 119 | 2.86 | 2.22 | 18.85 | 17.51 | 1.36 | 26 |
| 4 | 8153 | 0 | 4096 | 1916 | 2.63 | 2.14 | 16.79 | 15.29 | 1.38 | 614 |
| 5 | 2578 | 0 | 2048 | 994 | 2.55 | 2.06 | 16.62 | 15.19 | 1.32 | 430 |
| 6 | 21834 | 0 | 8192 | 3319 | 2.94 | 2.47 | 17.45 | 15.74 | 1.60 | 1360 |
| 7 | 21809 | 16384 | 4096 | 1719 | 2.84 | 2.38 | 17.10 | 15.44 | 1.54 | 687 |
| 8 | 2513 | 0 | 2048 | 1005 | 2.50 | 2.04 | 16.39 | 14.98 | 1.30 | 503 |
| 9 | 4810 | 0 | 4096 | 1809 | 2.79 | 2.26 | 17.22 | 15.69 | 1.42 | 709 |
| 10 | 3066 | 0 | 553 | 272 | 2.76 | 2.03 | 16.97 | 15.52 | 1.39 | 129 |
| 11 | 13064 | 0 | 4096 | 1674 | 3.04 | 2.45 | 17.88 | 16.19 | 1.57 | 459 |
| 12 | 35908 | 0 | 8192 | 3482 | 2.77 | 2.35 | 17.68 | 15.96 | 1.60 | 1317 |
| 13 | 137 | 0 | 4096 | 1736 | 2.86 | 2.36 | 15.82 | 14.32 | 1.39 | 809 |
| 14 | 151 | 0 | 4096 | 2536 | 2.01 | 1.62 | 13.85 | 12.62 | 1.13 | 1857 |

### Stage table (GPU stamps, ms per window; pooled over each group's windows)

| stage | ldr | math | code |
|---|---|---|---|
| hyper-connection reads (both; FFN read = the mixer read's time) | 2.49 | 2.50 | 2.40 |
| router / ring / hits | 0.50 | 0.50 | 0.47 |
| plan wait (waitA) | 0.28 | 0.27 | 0.26 |
| shared expert + expert inputs | 0.82 | 0.82 | 0.77 |
| routed experts on the 5080 (VRAM hits) | 2.31 | 2.56 | 1.98 |
| PCIe stage (empty) | 0.27 | 0.27 | 0.26 |
| **wait for the CPU (waitCPU)** | 4.11 | 2.70 | 1.96 |
| CPU rows + combine | 0.45 | 0.42 | 0.41 |
| GDN mixer (36 layers) | 2.38 | 2.38 | 2.31 |
| QSA mixer (12 layers) | 1.42 | 1.23 | 1.14 |
| head | 0.64 | 0.65 | 0.63 |
| gaps | 0.03 | 0.03 | 0.03 |
| GPU stage total | 15.71 | 14.32 | 12.62 |
| draft round (host) | 1.50 | 1.39 | 1.13 |
| commit + emit (host) | 0.01 | 0.01 | 0.01 |
| **window, host clock** | 17.32 | 15.82 | 13.85 |
| tokens per window | 2.29 | 2.36 | 1.62 |

### The CPU path, ms per window (summed over the 48 layers; pooled)

| part | ldr | math | code |
|---|---|---|---|
| reach | 7.591 | 7.728 | 7.344 |
| host | 7.452 | 5.919 | 4.613 |
| plan | 0.471 | 0.432 | 0.407 |
| helper-begin | 0.419 | 0.382 | 0.375 |
| actq | 0.000 | 0.000 | 0.000 |
| jobs | 0.047 | 0.035 | 0.029 |
| pool | 6.487 | 4.919 | 3.377 |
| gu | 3.880 | 2.930 | 2.021 |
| midq | 0.043 | 0.032 | 0.023 |
| down | 2.536 | 1.930 | 1.312 |
| park | 0.014 | 0.013 | 0.011 |
| helper-finish | 0.422 | 0.507 | 0.772 |
| waitA | 0.272 | 0.267 | 0.265 |
| waitCPU | 4.101 | 2.689 | 1.955 |
### helper 1500 slots
requests parsed: 15

| # | prompt | reused | generated | windows | avg T | tok/window | ms/window | GPU stage total | draft | helper wait ms |
|---|---|---|---|---|---|---|---|---|---|---|
| 0 | 9657 | 0 | 1 | 1 | 1.00 | 1.00 | 22.43 | 25.22 | 0.00 | 0 |
| 1 | 180 | 0 | 246 | 91 | 3.27 | 2.70 | 23.16 | 21.49 | 1.48 | 7 |
| 2 | 19372 | 0 | 8192 | 3821 | 2.61 | 2.14 | 17.94 | 16.36 | 1.46 | 633 |
| 3 | 171 | 0 | 271 | 109 | 3.08 | 2.49 | 21.65 | 20.24 | 1.40 | 8 |
| 4 | 8153 | 0 | 4096 | 1884 | 2.67 | 2.17 | 17.79 | 16.27 | 1.40 | 316 |
| 5 | 2578 | 0 | 2048 | 1041 | 2.48 | 1.97 | 16.93 | 15.53 | 1.29 | 215 |
| 6 | 21834 | 0 | 8192 | 3315 | 2.91 | 2.47 | 18.23 | 16.52 | 1.59 | 651 |
| 7 | 21809 | 16384 | 4096 | 1625 | 3.03 | 2.52 | 18.42 | 16.70 | 1.61 | 309 |
| 8 | 2513 | 0 | 2048 | 967 | 2.59 | 2.12 | 17.21 | 15.77 | 1.34 | 245 |
| 9 | 4810 | 0 | 4096 | 1867 | 2.73 | 2.19 | 17.71 | 16.19 | 1.40 | 383 |
| 10 | 3066 | 0 | 317 | 164 | 2.80 | 1.93 | 18.92 | 17.49 | 1.42 | 23 |
| 11 | 13064 | 0 | 4096 | 1725 | 3.02 | 2.37 | 18.73 | 17.05 | 1.56 | 219 |
| 12 | 35908 | 0 | 8192 | 3427 | 2.86 | 2.39 | 18.61 | 16.87 | 1.63 | 640 |
| 13 | 137 | 0 | 4096 | 1809 | 2.82 | 2.26 | 15.94 | 14.46 | 1.38 | 481 |
| 14 | 151 | 0 | 4096 | 2304 | 2.21 | 1.78 | 14.99 | 13.69 | 1.19 | 807 |

### Stage table (GPU stamps, ms per window; pooled over each group's windows)

| stage | ldr | math | code |
|---|---|---|---|
| hyper-connection reads (both; FFN read = the mixer read's time) | 2.49 | 2.50 | 2.40 |
| router / ring / hits | 0.51 | 0.50 | 0.48 |
| plan wait (waitA) | 0.27 | 0.26 | 0.27 |
| shared expert + expert inputs | 0.83 | 0.82 | 0.78 |
| routed experts on the 5080 (VRAM hits) | 2.37 | 2.62 | 2.15 |
| PCIe stage (empty) | 0.27 | 0.27 | 0.26 |
| **wait for the CPU (waitCPU)** | 4.85 | 2.80 | 2.77 |
| CPU rows + combine | 0.46 | 0.42 | 0.42 |
| GDN mixer (36 layers) | 2.38 | 2.38 | 2.34 |
| QSA mixer (12 layers) | 1.43 | 1.23 | 1.16 |
| head | 0.65 | 0.65 | 0.63 |
| gaps | 0.03 | 0.03 | 0.03 |
| GPU stage total | 16.52 | 14.46 | 13.69 |
| draft round (host) | 1.50 | 1.38 | 1.19 |
| commit + emit (host) | 0.01 | 0.01 | 0.01 |
| **window, host clock** | 18.14 | 15.94 | 14.99 |
| tokens per window | 2.29 | 2.26 | 1.78 |

### The CPU path, ms per window (summed over the 48 layers; pooled)

| part | ldr | math | code |
|---|---|---|---|
| reach | 7.649 | 7.945 | 7.545 |
| host | 8.203 | 5.836 | 5.476 |
| plan | 0.431 | 0.364 | 0.360 |
| helper-begin | 0.378 | 0.314 | 0.321 |
| actq | 0.000 | 0.000 | 0.000 |
| jobs | 0.039 | 0.026 | 0.026 |
| pool | 7.485 | 5.128 | 4.683 |
| gu | 4.482 | 3.062 | 2.802 |
| midq | 0.049 | 0.033 | 0.032 |
| down | 2.925 | 2.008 | 1.825 |
| park | 0.014 | 0.013 | 0.012 |
| helper-finish | 0.222 | 0.294 | 0.379 |
| waitA | 0.271 | 0.267 | 0.269 |
| waitCPU | 4.845 | 2.792 | 2.763 |
### helper 3600 slots
requests parsed: 0

| # | prompt | reused | generated | windows | avg T | tok/window | ms/window | GPU stage total | draft | helper wait ms |
|---|---|---|---|---|---|---|---|---|---|---|

### Stage table (GPU stamps, ms per window; pooled over each group's windows)

| stage | ldr | math | code |
|---|---|---|---|
| draft round (host) | 0.00 | 0.00 | 0.00 |
| commit + emit (host) | 0.00 | 0.00 | 0.00 |
| **window, host clock** | 0.00 | 0.00 | 0.00 |
| tokens per window | 0.00 | 0.00 | 0.00 |

### The CPU path, ms per window (summed over the 48 layers; pooled)

| part | ldr | math | code |
|---|---|---|---|
| reach | 0.000 | 0.000 | 0.000 |
| host | 0.000 | 0.000 | 0.000 |
| plan | 0.000 | 0.000 | 0.000 |
| helper-begin | 0.000 | 0.000 | 0.000 |
| actq | 0.000 | 0.000 | 0.000 |
| jobs | 0.000 | 0.000 | 0.000 |
| pool | 0.000 | 0.000 | 0.000 |
| gu | 0.000 | 0.000 | 0.000 |
| midq | 0.000 | 0.000 | 0.000 |
| down | 0.000 | 0.000 | 0.000 |
| park | 0.000 | 0.000 | 0.000 |
| helper-finish | 0.000 | 0.000 | 0.000 |
| waitA | 0.000 | 0.000 | 0.000 |
| waitCPU | 0.000 | 0.000 | 0.000 |
| cpu-entries | 0.000 | 0.000 | 0.000 |
| cpu-experts | 0.000 | 0.000 | 0.000 |
| pool overhead = pool − gu − midq − down | 0.000 | 0.000 | 0.000 |
| mean worker wake-up (µs, per phase) | 0.0 | 0.0 | 0.0 |
