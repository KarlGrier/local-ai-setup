
### C3p-v36-math vs C3p-fk-math (ms per verify window)

| stage | ours (base) | fork | fork − ours |
|---|---|---|---|
| router / ring / hits | 0.45 | 0.76 | +0.31 |
| wait for the pool's plan | 0.25 | 0.03 | -0.22 |
| shared expert + expert inputs | 0.94 | 0.09 | -0.85 |
| shared expert (on its own branch, beside) | – | 2.26 |  |
| routed experts (VRAM) | 2.69 | 2.85 | +0.16 |
| routed experts (PCIe stage) | 0.34 | 0.03 | -0.32 |
| wait for the CPU | 3.64 | 3.18 | -0.46 |
| wait for the second GPU | – | 40.18 |  |
| CPU rows + combine | 0.39 | 0.23 | -0.16 |
| GDN mixer | 3.01 | 2.40 | -0.61 |
| QSA mixer | 1.72 | 0.85 | -0.87 |
| hyper-connection reads | 3.14 | 2.37 | -0.77 |
| window inputs | – | 0.01 |  |
| head | 0.74 | 0.35 | -0.39 |
| gaps | 0.03 | 0.02 | -0.01 |
| total | 17.34 | 53.34 | +36.00 |
| host: draft round | 1.36 | 1.02 | -0.34 |
| host: commit | 0.01 | 0.04 | +0.03 |
| tokens per round | 2.53 | 2.54 | +0.01 |
| decode tok/s | 133.00 | 45.68 | -87.32 |

### C3p-v36-code vs C3p-fk-code (ms per verify window)

| stage | ours (base) | fork | fork − ours |
|---|---|---|---|
| router / ring / hits | 0.44 | 0.72 | +0.28 |
| wait for the pool's plan | 0.26 | 0.03 | -0.23 |
| shared expert + expert inputs | 0.88 | 0.09 | -0.79 |
| shared expert (on its own branch, beside) | – | 1.88 |  |
| routed experts (VRAM) | 2.26 | 2.40 | +0.14 |
| routed experts (PCIe stage) | 0.32 | 0.03 | -0.29 |
| wait for the CPU | 2.60 | 1.97 | -0.63 |
| wait for the second GPU | – | 35.46 |  |
| CPU rows + combine | 0.39 | 0.22 | -0.17 |
| GDN mixer | 2.81 | 2.37 | -0.44 |
| QSA mixer | 1.63 | 0.83 | -0.80 |
| hyper-connection reads | 2.84 | 2.28 | -0.56 |
| window inputs | – | 0.01 |  |
| head | 0.69 | 0.35 | -0.34 |
| gaps | 0.03 | 0.02 | -0.01 |
| total | 15.14 | 46.79 | +31.65 |
| host: draft round | 1.14 | 0.87 | -0.27 |
| host: commit | 0.01 | 0.05 | +0.04 |
| tokens per round | 1.88 | 2.07 | +0.19 |
| decode tok/s | 113.21 | 42.65 | -70.56 |
