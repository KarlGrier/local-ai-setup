| arm | workload | n | tokens | decode tok/s (client) | decode tok/s (engine) | accepted / drafted | expert-cache hit % | prompt tok/s | finish |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| a1s7 | C-conv | 2 | 1049.0 | 123.5 | 123.4 | 1280/1954 (66%) | 70.5 | 117.6 | stop |
| a1s7 | C-struct | 1 | 7230 | 174.2 | 174.2 | 5376/5616 (96%) | 75.6 | 282.0 | stop |
| a1s7 | C-prose | 2 | 1006.0 | 115.3 | 115.2 | 1071/2138 (50%) | 75.8 | 97.3 | length,stop |
| c1cal | C-conv | 2 | 1061.5 | 126.4 | 125.9 | 1321/1796 (74%) | 69.7 | 127.2 | stop |
| c1cal | C-struct | 1 | 7230 | 194.5 | 194.4 | 6127/6326 (97%) | 75.2 | 344.3 | stop |
| c1cal | C-prose | 2 | 1152.0 | 130.3 | 130.1 | 1245/1839 (68%) | 77.6 | 106.7 | length,stop |

- a1s7: experts in VRAM at start: 4433 slots / 8.46 GiB
- c1cal: experts in VRAM at start: -
