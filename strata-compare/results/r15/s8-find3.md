# Round 15 step 8 — where C*15's ~3 % went (decode screen, one arm each, interleaved; your sampling)

C*14 arms: 145.8 / 144.5 / 145.0 → mean **145.1**; plain C*15 arms: 140.2 / 143.3 → mean **141.8** (-2.3 %)

| arm (in order) | decode tok/s | vs C*14 mean | vs C*15 mean |
|---|---|---|---|
| r15-f3b-1-c14 | 145.8 | +0.5 % | +2.8 % |
| r15-f3b-2-c15 | 140.2 | -3.3 % | -1.1 % |
| r15-f3b-3-costgate0 | 137.1 | -5.5 % | -3.3 % |
| r15-f3b-4-stager0 | 141.1 | -2.7 % | -0.5 % |
| r15-f3b-5-pinguard0 | 140.9 | -2.9 % | -0.6 % |
| r15-f3b-6-c14 | 144.5 | -0.4 % | +1.9 % |
| r15-f3b-7-streamahead0 | 141.0 | -2.9 % | -0.6 % |
| r15-f3b-8-noq8kavx2 | 141.4 | -2.6 % | -0.3 % |
| r15-f3b-9-mmvqil0 | 139.2 | -4.0 % | -1.8 % |
| r15-f3b-10-c15 | 143.3 | -1.2 % | +1.1 % |
| r15-f3b-11-c14 | 145.0 | -0.1 % | +2.3 % |
