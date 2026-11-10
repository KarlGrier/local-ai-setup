basalt-bench  build f0bb833c49  power limit 360 W

| test      |  t/s | accept % | draft len |
| --------- | ---: | -------: | --------: |
| pp16384   | 5362 |        - |         - |
| pp65536   | 5439 |        - |         - |
| tg conv   |  161 |     71.8 |      2.32 |
| tg struct |  245 |     94.4 |      6.84 |
| tg prose  |  154 |     64.3 |      1.71 |

hardware (measured before the engine starts)
  CPU   AMD Ryzen 9 9950X3D, 16 cores
  RAM   read 76.4 GB/s
  GPU   RTX 5080  PCIe 5.0 x16  host-to-device 57.3 GB/s

community-1: prefill 16K 5361.5 t/s (3.1 s), prefill 64K 5438.6 t/s (12.2 s), decode 216.0 t/s (9503 tokens in 44.0 s), each measured cold

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
          "h2d_gbps": 57.3
        }
      ],
      "ram_gib": 92,
      "cpu": "AMD Ryzen 9 9950X3D, 16 cores",
      "ram_gbps": 76.4,
      "os": "Linux",
      "quant": "IQ3_S",
      "prefill_16k_tps": 5361.5,
      "prefill_64k_tps": 5438.6,
      "decode_tps": 216.0
    }
2026-11-02T03:01:37 basalt020-comm-3 exit=0 90s min_MemAvailable=33.1GiB@86s min_5080_free=580MiB@16s max_tree_RSS=50.0GiB max_swap_used=0.00GiB min_4060Ti_free=7875MiB ok
