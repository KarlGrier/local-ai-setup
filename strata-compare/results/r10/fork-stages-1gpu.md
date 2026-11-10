
### C3s-v36-math vs C3s-fk-math (ms per verify window)

| stage | ours (base) | fork | fork − ours |
|---|---|---|---|
| router / ring / hits | 0.44 | 0.74 | +0.30 |
| wait for the pool's plan | 0.25 | 0.03 | -0.22 |
| shared expert + expert inputs | 0.94 | 0.10 | -0.84 |
| shared expert (on its own branch, beside) | – | 1.68 |  |
| routed experts (VRAM) | 2.74 | 3.03 | +0.29 |
| routed experts (PCIe stage) | 0.33 | 0.03 | -0.30 |
| wait for the CPU | 5.16 | 12.41 | +7.25 |
| wait for the second GPU | – | 0.02 |  |
| CPU rows + combine | 0.41 | 0.27 | -0.14 |
| GDN mixer | 3.03 | 2.39 | -0.64 |
| QSA mixer | 1.73 | 0.84 | -0.89 |
| hyper-connection reads | 3.18 | 2.32 | -0.86 |
| window inputs | – | 0.02 |  |
| head | 0.75 | 0.61 | -0.14 |
| gaps | 0.03 | 0.03 | -0.00 |
| total | 18.98 | 22.85 | +3.87 |
| host: draft round | 1.36 | 1.14 | -0.22 |
| host: commit | 0.01 | 0.04 | +0.03 |
| tokens per round | 2.64 | 2.61 | -0.03 |
| decode tok/s | 127.55 | 107.34 | -20.21 |

### C3s-v36-code vs C3s-fk-code (ms per verify window)

| stage | ours (base) | fork | fork − ours |
|---|---|---|---|
| router / ring / hits | 0.45 | 0.68 | +0.23 |
| wait for the pool's plan | 0.25 | 0.03 | -0.22 |
| shared expert + expert inputs | 0.87 | 0.08 | -0.79 |
| shared expert (on its own branch, beside) | – | 1.38 |  |
| routed experts (VRAM) | 2.15 | 2.50 | +0.35 |
| routed experts (PCIe stage) | 0.31 | 0.03 | -0.28 |
| wait for the CPU | 3.69 | 8.88 | +5.19 |
| wait for the second GPU | – | 0.02 |  |
| CPU rows + combine | 0.37 | 0.26 | -0.11 |
| GDN mixer | 2.75 | 2.36 | -0.39 |
| QSA mixer | 1.62 | 0.83 | -0.79 |
| hyper-connection reads | 2.74 | 2.23 | -0.52 |
| window inputs | – | 0.02 |  |
| head | 0.67 | 0.61 | -0.06 |
| gaps | 0.03 | 0.03 | -0.00 |
| total | 15.95 | 18.55 | +2.60 |
| host: draft round | 1.11 | 0.87 | -0.23 |
| host: commit | 0.01 | 0.04 | +0.03 |
| tokens per round | 1.80 | 1.97 | +0.17 |
| decode tok/s | 103.84 | 99.51 | -4.33 |
