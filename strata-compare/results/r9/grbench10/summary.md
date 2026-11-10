v5: run 1 vs run 2 bit-identical: True
v3: run 1 vs run 2 bit-identical: True
old: run 1 vs run 2 bit-identical: True
plain: run 1 vs run 2 bit-identical: True
v3 vs v5: lo 0/23040 identical, max rel 1.69e+06; rs 213/288 identical, max rel 1.19e-07; inject 22/288 identical, max rel 5.93e-05; mixed 102475/184320 identical, max rel 3.28e-03; R 737280/737280 identical, max rel 0.00e+00
old vs v5: lo 6004/23040 identical, max rel 2.41e-03; rs 288/288 identical, max rel 0.00e+00; inject 56/288 identical, max rel 1.39e-05; mixed 136988/184320 identical, max rel 5.75e-04; R 737280/737280 identical, max rel 0.00e+00
v3 vs old: lo 0/23040 identical, max rel 1.69e+06; rs 213/288 identical, max rel 1.19e-07; inject 40/288 identical, max rel 4.54e-05; mixed 101062/184320 identical, max rel 3.28e-03; R 737280/737280 identical, max rel 0.00e+00
plain vs old: lo 23040/23040 identical, max rel 0.00e+00; rs 288/288 identical, max rel 0.00e+00; inject 288/288 identical, max rel 0.00e+00; mixed 184320/184320 identical, max rel 0.00e+00; R 737280/737280 identical, max rel 0.00e+00
plain vs v5: lo 6004/23040 identical, max rel 2.41e-03; rs 288/288 identical, max rel 0.00e+00; inject 56/288 identical, max rel 1.39e-05; mixed 136988/184320 identical, max rel 5.75e-04; R 737280/737280 identical, max rel 0.00e+00

| T | apply | v5 cold / warm µs | v3 cold / warm µs | old cold / warm µs | plain cold / warm µs | v3 vs v5 (cold) |
|---|---|---|---|---|---|---|
| 1 | 1 | 30.7 / 15.9 | 26.6 / 14.2 | 38.6 / 21.9 | 38.6 / 21.9 | -13.3 % |
| 2 | 1 | 34.5 / 19.8 | 30.4 / 17.0 | 41.3 / 26.0 | 41.3 / 26.0 | -11.8 % |
| 3 | 1 | 36.7 / 23.9 | 34.8 / 21.9 | 44.8 / 30.1 | 44.8 / 30.1 | -5.2 % |
| 4 | 1 | 38.9 / 26.0 | 38.9 / 25.1 | 49.1 / 34.2 | 49.1 / 34.2 | +0.0 % |
| 5 | 1 | 44.7 / 32.1 | 53.2 / 32.6 | 52.9 / 38.4 | 52.9 / 38.4 | +19.0 % |
| 6 | 1 | 47.5 / 36.3 | 57.3 / 37.4 | 56.8 / 42.5 | 56.0 / 42.5 | +20.8 % |
| 7 | 1 | 50.9 / 38.3 | 63.4 / 42.8 | 61.1 / 48.3 | 61.1 / 48.4 | +24.5 % |
| 8 | 1 | 53.1 / 42.4 | 67.6 / 47.7 | 65.2 / 52.6 | 65.2 / 52.5 | +27.3 % |
| 1 | 0 | 30.4 / 15.6 | 26.3 / 12.6 | 36.9 / 19.9 | 36.9 / 19.9 | -13.5 % |
| 2 | 0 | 32.8 / 17.9 | 28.7 / 16.9 | 40.6 / 24.0 | 40.6 / 24.0 | -12.5 % |
| 3 | 0 | 34.7 / 21.9 | 32.8 / 20.3 | 42.7 / 28.0 | 42.7 / 28.0 | -5.5 % |
| 4 | 0 | 37.4 / 24.0 | 36.9 / 23.1 | 47.1 / 32.2 | 47.1 / 32.2 | -1.4 % |
| 5 | 0 | 42.7 / 30.1 | 51.2 / 29.1 | 50.9 / 36.3 | 50.9 / 36.3 | +19.9 % |
| 6 | 0 | 47.0 / 34.2 | 55.3 / 33.3 | 53.4 / 40.4 | 53.4 / 40.4 | +17.8 % |
| 7 | 0 | 49.0 / 36.3 | 59.4 / 38.3 | 59.1 / 44.5 | 59.2 / 44.5 | +21.2 % |
| 8 | 0 | 50.9 / 39.5 | 65.2 / 41.5 | 63.2 / 48.6 | 63.0 / 48.6 | +28.1 % |
