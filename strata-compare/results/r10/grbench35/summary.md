v5: run 1 vs run 2 bit-identical: True
v3: run 1 vs run 2 bit-identical: True
old: run 1 vs run 2 bit-identical: True
plain: run 1 vs run 2 bit-identical: True
max4: run 1 vs run 2 bit-identical: True
max4plain: run 1 vs run 2 bit-identical: True
v3 vs v5: lo 0/23040 identical, max rel 1.69e+06; rs 213/288 identical, max rel 1.19e-07; inject 22/288 identical, max rel 5.93e-05; mixed 102475/184320 identical, max rel 3.28e-03; R 737280/737280 identical, max rel 0.00e+00
old vs v5: lo 6004/23040 identical, max rel 2.41e-03; rs 288/288 identical, max rel 0.00e+00; inject 56/288 identical, max rel 1.39e-05; mixed 136988/184320 identical, max rel 5.75e-04; R 737280/737280 identical, max rel 0.00e+00
v3 vs old: lo 0/23040 identical, max rel 1.69e+06; rs 213/288 identical, max rel 1.19e-07; inject 40/288 identical, max rel 4.54e-05; mixed 101062/184320 identical, max rel 3.28e-03; R 737280/737280 identical, max rel 0.00e+00
plain vs old: lo 23040/23040 identical, max rel 0.00e+00; rs 288/288 identical, max rel 0.00e+00; inject 288/288 identical, max rel 0.00e+00; mixed 184320/184320 identical, max rel 0.00e+00; R 737280/737280 identical, max rel 0.00e+00
plain vs v5: lo 6004/23040 identical, max rel 2.41e-03; rs 288/288 identical, max rel 0.00e+00; inject 56/288 identical, max rel 1.39e-05; mixed 136988/184320 identical, max rel 5.75e-04; R 737280/737280 identical, max rel 0.00e+00
max4 vs old: lo 23040/23040 identical, max rel 0.00e+00; rs 288/288 identical, max rel 0.00e+00; inject 288/288 identical, max rel 0.00e+00; mixed 184320/184320 identical, max rel 0.00e+00; R 737280/737280 identical, max rel 0.00e+00
max4plain vs plain: lo 23040/23040 identical, max rel 0.00e+00; rs 288/288 identical, max rel 0.00e+00; inject 288/288 identical, max rel 0.00e+00; mixed 184320/184320 identical, max rel 0.00e+00; R 737280/737280 identical, max rel 0.00e+00
max4 vs v3: lo 0/23040 identical, max rel 1.00e+00; rs 213/288 identical, max rel 1.19e-07; inject 40/288 identical, max rel 4.54e-05; mixed 101062/184320 identical, max rel 3.29e-03; R 737280/737280 identical, max rel 0.00e+00

| T | apply | v5 cold / warm µs | v3 cold / warm µs | old cold / warm µs | plain cold / warm µs | max4 cold / warm µs | max4plain cold / warm µs | v3 vs v5 (cold) | max4 vs v3 (cold) |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 1 | 30.7 / 15.8 | 26.6 / 14.2 | 36.9 / 22.0 | 38.9 / 21.9 | 34.7 / 19.9 | 36.9 / 19.9 | -13.3 % | +30.3 % |
| 2 | 1 | 34.5 / 19.9 | 30.4 / 17.0 | 40.8 / 28.2 | 41.3 / 26.0 | 38.6 / 26.0 | 40.6 / 24.0 | -11.8 % | +26.8 % |
| 3 | 1 | 36.7 / 23.9 | 34.8 / 21.9 | 44.8 / 34.2 | 45.1 / 30.1 | 41.0 / 30.1 | 44.3 / 28.1 | -5.2 % | +17.6 % |
| 4 | 1 | 38.9 / 26.0 | 38.9 / 25.1 | 49.1 / 38.4 | 49.1 / 34.3 | 45.1 / 36.3 | 48.9 / 34.2 | +0.0 % | +15.8 % |
| 5 | 1 | 44.8 / 32.2 | 53.2 / 32.5 | 52.9 / 44.5 | 52.9 / 38.4 | 52.9 / 44.5 | 52.9 / 38.3 | +19.0 % | -0.6 % |
| 6 | 1 | 47.1 / 36.3 | 57.3 / 37.4 | 57.1 / 48.6 | 56.0 / 42.5 | 57.2 / 48.6 | 55.8 / 42.5 | +21.7 % | -0.2 % |
| 7 | 1 | 50.9 / 38.3 | 63.3 / 42.6 | 63.5 / 56.7 | 61.2 / 47.7 | 63.5 / 56.6 | 61.1 / 47.5 | +24.5 % | +0.3 % |
| 8 | 1 | 53.1 / 42.4 | 67.6 / 47.6 | 69.5 / 62.9 | 65.2 / 52.6 | 69.6 / 62.8 | 65.2 / 52.5 | +27.3 % | +3.0 % |
| 1 | 0 | 30.4 / 15.4 | 26.3 / 12.6 | 36.6 / 21.9 | 36.9 / 19.9 | 32.8 / 18.0 | 34.8 / 17.9 | -13.5 % | +24.6 % |
| 2 | 0 | 32.6 / 17.8 | 28.7 / 16.9 | 40.7 / 28.0 | 40.6 / 24.1 | 36.9 / 24.1 | 38.8 / 22.0 | -12.1 % | +28.6 % |
| 3 | 0 | 34.7 / 21.9 | 32.8 / 19.9 | 42.9 / 32.1 | 42.9 / 28.0 | 40.6 / 28.7 | 42.2 / 26.0 | -5.5 % | +24.0 % |
| 4 | 0 | 37.4 / 24.0 | 36.9 / 23.1 | 47.1 / 38.3 | 47.1 / 32.2 | 43.1 / 34.2 | 47.0 / 32.2 | -1.4 % | +17.0 % |
| 5 | 0 | 42.7 / 30.1 | 51.2 / 29.1 | 51.2 / 42.4 | 50.9 / 36.3 | 51.2 / 42.5 | 50.9 / 36.3 | +19.9 % | +0.0 % |
| 6 | 0 | 47.0 / 34.2 | 55.3 / 33.3 | 55.2 / 46.6 | 53.6 / 40.4 | 55.3 / 46.6 | 53.2 / 40.4 | +17.8 % | -0.0 % |
| 7 | 0 | 49.0 / 36.3 | 59.4 / 37.3 | 63.2 / 54.7 | 59.4 / 44.5 | 63.2 / 54.7 | 59.3 / 44.5 | +21.2 % | +6.4 % |
| 8 | 0 | 50.9 / 39.1 | 65.2 / 41.5 | 67.6 / 60.8 | 62.8 / 48.6 | 67.6 / 60.8 | 63.2 / 48.6 | +28.1 % | +3.6 % |
