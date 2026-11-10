# c171-iq3s-quick (A) vs c18-iq3s-quick (B): item by item

Items fingerprints: A `0e077e7e4ad53eba`, B `0e077e7e4ad53eba`

Difference = B - A in score points, on the items both have; paired bootstrap 95 % interval; sign-flip permutation p. 'within noise' = the interval contains 0 or p >= 0.05.

| Category | shared items | A % | B % | B - A | 95 % interval | p | items B better / A better | verdict |
|---|---|---|---|---|---|---|---|---|
| Coding (hidden tests) | 25 | 81.1 | 88.2 | 7.1 | -7.8 to 22.9 | 0.453 | 4 / 3 | **within noise** |
| Agentic coding (repos green) | 3 | 100.0 | 100.0 | 0.0 | 0.0 to 0.0 | 1.000 | 0 / 0 | **within noise** |
| Math | 20 | 95.0 | 100.0 | 5.0 | 0.0 to 15.0 | 1.000 | 1 / 0 | **within noise** |
| Instruction following | 20 | 100.0 | 95.0 | -5.0 | -15.0 to 0.0 | 1.000 | 0 / 1 | **within noise** |
| Tool calls | 10 | 100.0 | 100.0 | 0.0 | 0.0 to 0.0 | 1.000 | 0 / 0 | **within noise** |
| Long context | 6 | 66.7 | 83.3 | 16.7 | 0.0 to 50.0 | 1.000 | 1 / 0 | **within noise** |
| Honesty (balanced) | 20 | 66.7 | 73.3 | 6.7 | 0.0 to 16.7 | 0.500 | 2 / 0 | **within noise** |
| Research with web search (key) | 7 | 78.6 | 85.7 | 7.1 | -35.7 to 50.0 | 1.000 | 2 / 1 | **within noise** (A: r04_strata_release fixed upstream in 0.1.43.1) |

Efficiency (output tokens / wall seconds per solved item):

| Category | A | B |
|---|---|---|
| Coding (hidden tests) | 24,403 / 181 | 26,118 / 199 |
| Agentic coding (repos green) | 4,678 / 36 | 4,833 / 38 |
| Math | 10,377 / 69 | 9,684 / 65 |
| Instruction following | 521 / 4 | 610 / 5 |
| Tool calls | 113 / 1 | 108 / 1 |
| Long context | 23,876 / 159 | 20,406 / 135 |
| Honesty (balanced) | 28,605 / 213 | 19,121 / 144 |
| Research with web search (key) | 5,366 / 51 | 5,542 / 44 |
