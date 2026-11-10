
base (chat, the user's sampling; median of 2 reps):
| N | total tok/s | per request tok/s (median / slowest) | first token median / worst s | prompt tok/s (median) | wall s | min MemAvailable GiB | all at max_tokens |
|---|---|---|---|---|---|---|---|
| 1 | 124.0 | 137.9 / 137.9 | 0.42 / 0.42 | 137 | 4.1 | 32.0 | yes |
| 2 | 118.9 | 131.8 / 130.1 | 2.55 / 4.68 | 71 | 8.6 | 32.0 | yes |
| 4 | 125.6 | 139.8 / 128.3 | 6.38 / 12.31 | 11 | 16.3 | 32.0 | yes |

b4 (chat, the user's sampling; median of 2 reps):
| N | total tok/s | per request tok/s (median / slowest) | first token median / worst s | prompt tok/s (median) | wall s | min MemAvailable GiB | all at max_tokens |
|---|---|---|---|---|---|---|---|
| 1 | 109.8 | 121.6 / 121.6 | 0.45 / 0.45 | 129 | 4.7 | 25.1 | yes |
| 2 | 96.8 | 51.8 / 50.6 | 0.67 / 0.92 | 96 | 10.6 | 25.1 | yes |
| 4 | 115.7 | 31.1 / 29.9 | 1.21 / 1.93 | 47 | 17.7 | 25.1 | yes |

b4mtp (chat, the user's sampling; median of 2 reps):
| N | total tok/s | per request tok/s (median / slowest) | first token median / worst s | prompt tok/s (median) | wall s | min MemAvailable GiB | all at max_tokens |
|---|---|---|---|---|---|---|---|
| 2 | 101.6 | 56.8 / 53.4 | 0.76 / 1.03 | 85 | 10.1 | 24.4 | yes |
| 4 | 116.0 | 32.2 / 30.2 | 1.23 / 2.03 | 51 | 17.7 | 24.5 | yes |

base (agent, the user's sampling; median of 2 reps):
| N | total tok/s | per request tok/s (median / slowest) | first token median / worst s | prompt tok/s (median) | wall s | min MemAvailable GiB | all at max_tokens |
|---|---|---|---|---|---|---|---|
| 1 | 58.6 | 133.2 / 133.2 | 4.90 / 4.90 | 3752 | 8.7 | 25.1 | yes |
| 2 | 59.9 | 138.3 / 135.6 | 9.16 / 13.43 | 2525 | 17.1 | 25.6 | yes |
| 4 | 59.8 | 137.8 / 130.2 | 17.77 / 30.38 | 1085 | 34.2 | 26.6 | yes |

b4 (agent, the user's sampling; median of 2 reps):
| N | total tok/s | per request tok/s (median / slowest) | first token median / worst s | prompt tok/s (median) | wall s | min MemAvailable GiB | all at max_tokens |
|---|---|---|---|---|---|---|---|
| 1 | 57.7 | 118.1 / 118.1 | 4.53 / 4.53 | 4060 | 8.9 | 21.5 | yes |
| 2 | 53.0 | 46.4 / 36.4 | 7.33 / 10.23 | 2938 | 19.3 | 21.5 | yes |
| 4 | 58.4 | 24.6 / 18.5 | 13.18 / 21.95 | 1453 | 35.1 | 21.8 | yes |

b4mtp (agent, the user's sampling; median of 2 reps):
| N | total tok/s | per request tok/s (median / slowest) | first token median / worst s | prompt tok/s (median) | wall s | min MemAvailable GiB | all at max_tokens |
|---|---|---|---|---|---|---|---|
| 2 | 58.1 | 55.1 / 41.1 | 7.37 / 10.22 | 2881 | 17.6 | 21.1 | yes |
| 4 | 61.1 | 26.4 / 19.8 | 13.07 / 21.66 | 1466 | 33.5 | 21.6 | yes |
