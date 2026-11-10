basalt-bench  build f0bb833c49  power limit 360 W

| test      |  t/s | accept % | draft len |
| --------- | ---: | -------: | --------: |
| pp16384   | 5343 |        - |         - |
| pp65536   | 5438 |        - |         - |
| tg conv   |  156 |     70.5 |      2.27 |
| tg struct |  247 |     95.9 |      6.66 |
| tg prose  |  162 |     67.8 |      1.88 |

hardware (measured before the engine starts)
  CPU   AMD Ryzen 9 9950X3D, 16 cores
  RAM   read 77.2 GB/s
  GPU   RTX 5080  PCIe 5.0 x16  host-to-device 57.8 GB/s

community-1: prefill 16K 5342.6 t/s (3.1 s), prefill 64K 5438.2 t/s (12.2 s), decode 217.8 t/s (9513 tokens in 43.7 s), each measured cold

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
          "h2d_gbps": 57.8
        }
      ],
      "ram_gib": 92,
      "cpu": "AMD Ryzen 9 9950X3D, 16 cores",
      "ram_gbps": 77.2,
      "os": "Linux",
      "quant": "IQ3_S",
      "prefill_16k_tps": 5342.6,
      "prefill_64k_tps": 5438.2,
      "decode_tps": 217.8
    }
2026-11-02T03:00:04 basalt020-comm-2 exit=0 89s min_MemAvailable=33.1GiB@88s min_5080_free=580MiB@16s max_tree_RSS=50.0GiB max_swap_used=0.00GiB min_4060Ti_free=7875MiB ok
