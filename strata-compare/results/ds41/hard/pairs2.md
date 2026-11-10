# Repeat pairs with DSpark off; carry-over with placement frozen (10-27)

- Repeat pairs (v026test, counter reset, REUSE=0, placement frozen, --dspark none): identical {'jan1024': False, 'jan4096': False, 'w1': False, 'w1k': False} (10-26 with --dspark auto: none identical) - /home/USER/ai-speed-testing/strata-compare/results/ds41/tuning/rep-test-reuse0-nodspark-1027-0147
- Carry-over, expert cache on (hard set, 10-27 01:28), window 128: {"positions": 2047, "identical": false, "first_difference": 0, "kl_mean": 0.00408, "top1_changed": 15, "kl_by_pos": {"0-16": 0.2813, "16-128": 0.0171, "128-512": 0.0011, "512-end": 0.001}}
- Carry-over, expert cache on (hard set, 10-27 01:28), window 1: {"positions": 2047, "identical": false, "first_difference": 0, "kl_mean": 0.00541, "top1_changed": 19, "kl_by_pos": {"0-16": 0.3576, "16-128": 0.0287, "128-512": 0.0022, "512-end": 0.0008}}
- Carry-over, placement frozen, window 128: {"positions": 2047, "identical": false, "first_difference": 0, "kl_mean": 0.00219, "top1_changed": 15, "kl_by_pos": {"0-16": 0.1035, "16-128": 0.0074, "128-512": 0.0019, "512-end": 0.0008}, "rc": 0}
- Carry-over, placement frozen, window 1: {"positions": 2047, "identical": true, "first_difference": null, "kl_mean": 0.0, "top1_changed": 0, "kl_by_pos": {"0-16": 0.0, "16-128": 0.0, "128-512": 0.0, "512-end": 0.0}, "rc": 0}
