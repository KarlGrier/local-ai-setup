basalt-bench  build f0bb833c49  power limit 360 W

| test      |  t/s | accept % | draft len |
| --------- | ---: | -------: | --------: |
| pp16384   | 4486 |        - |         - |
| pp65536   | 5442 |        - |         - |
| tg conv   |  157 |     72.1 |      2.62 |
| tg struct |  247 |     96.2 |      6.45 |
| tg prose  |  164 |     67.8 |      1.84 |

hardware (measured before the engine starts)
  CPU   AMD Ryzen 9 9950X3D, 16 cores
  RAM   read 76.6 GB/s
  GPU   RTX 5080  PCIe 5.0 x16  host-to-device 57.7 GB/s

community-1: prefill 16K 4486.3 t/s (3.7 s), prefill 64K 5442.2 t/s (12.2 s), decode 217.8 t/s (9630 tokens in 44.2 s), each measured cold

COMMUNITY ROW:
    {
      "submitter": "local-test",
      "date": "2026-11-02",
      "commit": "f0bb833c49",
      "preset": "community-1",
      "gpus": [
        {
          "name": "RTX 5080",
          "vram_gib": 16,
          "power_w": 360,
          "pcie": "5.0 x16",
          "h2d_gbps": 57.7
        }
      ],
      "ram_gib": 92,
      "cpu": "AMD Ryzen 9 9950X3D, 16 cores",
      "ram_gbps": 76.6,
      "os": "Linux",
      "quant": "IQ3_S",
      "prefill_16k_tps": 4486.3,
      "prefill_64k_tps": 5442.2,
      "decode_tps": 217.8
    }
2026-11-02T02:58:30 basalt020-comm-1 exit=0 90s min_MemAvailable=33.3GiB@89s min_5080_free=580MiB@17s max_tree_RSS=50.0GiB max_swap_used=0.00GiB min_4060Ti_free=7875MiB ok
