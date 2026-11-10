| share of the prompt | A2-32k-a (32768 tok, wall 10.41 s) | A2-32k-b (32768 tok, wall 10.43 s) | A2-112k-a (114687 tok, wall 35.47 s) | A2-112k-b (114687 tok, wall 35.50 s) |
|---|---|---|---|---|
| GDN mixer (proj in + conv/gates + recurrence + out proj) | 2517 ms (24.6 % of GPU) | 2525 ms (24.6 % of GPU) | 8744 ms (24.8 % of GPU) | 8745 ms (24.8 % of GPU) |
|   of which the recurrence | 775 ms (7.6 % of GPU) | 776 ms (7.6 % of GPU) | 2717 ms (7.7 % of GPU) | 2718 ms (7.7 % of GPU) |
| expert GEMMs (MMQ gate/up + down) | 2238 ms (21.9 % of GPU) | 2240 ms (21.8 % of GPU) | 7778 ms (22.0 % of GPU) | 7776 ms (22.0 % of GPU) |
| expert group copies (gather + 'dequant' + wait for stream copies) | 1565 ms (15.3 % of GPU) | 1569 ms (15.3 % of GPU) | 5500 ms (15.6 % of GPU) | 5501 ms (15.6 % of GPU) |
| QSA (proj + indexer + select + attn) | 1517 ms (14.8 % of GPU) | 1522 ms (14.8 % of GPU) | 6648 ms (18.8 % of GPU) | 6650 ms (18.8 % of GPU) |
| hyper-connection reads | 894 ms (8.7 % of GPU) | 896 ms (8.7 % of GPU) | 3042 ms (8.6 % of GPU) | 3042 ms (8.6 % of GPU) |
| router + shared expert + combine | 728 ms (7.1 % of GPU) | 729 ms (7.1 % of GPU) | 2496 ms (7.1 % of GPU) | 2505 ms (7.1 % of GPU) |
| embed + steps (per-chunk setup, first-use loading) | 724 ms (7.1 % of GPU) | 727 ms (7.1 % of GPU) | 777 ms (2.2 % of GPU) | 794 ms (2.2 % of GPU) |
| n-gram (PLE) on the GPU | 42 ms (0.4 % of GPU) | 44 ms (0.4 % of GPU) | 147 ms (0.4 % of GPU) | 147 ms (0.4 % of GPU) |
| KV stage | 11 ms (0.1 % of GPU) | 11 ms (0.1 % of GPU) | 166 ms (0.5 % of GPU) | 166 ms (0.5 % of GPU) |
| draft layer (host, after each chunk) | 694 ms (6.7 % of wall) | 696 ms (6.7 % of wall) | 698 ms (2.0 % of wall) | 698 ms (2.0 % of wall) |
| PLE (host) | 180 ms (1.7 % of wall) | 172 ms (1.6 % of wall) | 168 ms (0.5 % of wall) | 162 ms (0.5 % of wall) |
