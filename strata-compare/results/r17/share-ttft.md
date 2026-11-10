auto vs fixed 0.4:
| size | AUTO: TTFT ms (arm a / arm b) | AUTO: engine read ms | F04: TTFT ms (arm a / arm b) | F04: engine read ms | TTFT B vs A | read B vs A |
|---|---|---|---|---|---|---|
| 512 | 579 (582 / 576; n=12) | 547 | 576 (578 / 574; n=12) | 545 | -0.4 % | -0.4 % |
| 1000 | 716 (715 / 717; n=12) | 685 | 679 (681 / 677; n=12) | 648 | -5.2 % | -5.4 % |

auto vs off:
| size | AUTO: TTFT ms (arm a / arm b) | AUTO: engine read ms | OFF: TTFT ms (arm a / arm b) | OFF: engine read ms | TTFT B vs A | read B vs A |
|---|---|---|---|---|---|---|
| 512 | 579 (582 / 576; n=12) | 547 | 693 (694 / 693; n=12) | 664 | +19.8 % | +21.2 % |
| 1000 | 716 (715 / 717; n=12) | 685 | 864 (865 / 863; n=12) | 834 | +20.7 % | +21.8 % |

off vs fixed 0.4:
| size | OFF: TTFT ms (arm a / arm b) | OFF: engine read ms | F04: TTFT ms (arm a / arm b) | F04: engine read ms | TTFT B vs A | read B vs A |
|---|---|---|---|---|---|---|
| 512 | 693 (694 / 693; n=12) | 664 | 576 (578 / 574; n=12) | 545 | -16.9 % | -17.9 % |
| 1000 | 864 (865 / 863; n=12) | 834 | 679 (681 / 677; n=12) | 648 | -21.4 % | -22.3 % |
