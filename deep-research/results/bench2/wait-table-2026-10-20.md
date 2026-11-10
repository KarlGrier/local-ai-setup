# Research vs chat waits at the chosen level (medium) - 2026-10-20 03:15:00, tools/wait_table.py

```
runs: screen-deep-medium, screen-extra-deep-medium, hard-screen-deep-medium; 13.5 h of research
call duration by class: p50 / p90 / max (n)
  extract     8.7 /   20.3 /  280.4 s (1585; 4.9 h)
  agent       4.0 /   10.1 /  333.0 s (1510; 2.5 h)
  compact    64.4 /  118.8 /  166.1 s (125; 2.5 h)
  verify     32.4 /   49.9 /  338.1 s (159; 1.7 h)
  report     32.5 /   66.3 /  395.7 s (97; 1.0 h)
  other      40.4 /  111.9 /  187.6 s (36; 0.6 h)
chat wait, any moment of the run: p50 9 s, p90 59 s, over 60 s 10 %
chat wait, while a call is in flight (10-18 basis): p50 11 s, p90 65 s, over 60 s 11 %

runs: screen-deep, hard-screen-deep; 7.5 h of research
call duration by class: p50 / p90 / max (n)
  verify    107.4 /  182.6 /  356.5 s (100; 3.2 h)
  extract    33.3 /  146.8 /  296.3 s (171; 3.0 h)
  report     75.0 /  122.3 /  414.8 s (56; 1.3 h)
  agent       4.9 /   11.6 /  279.4 s (154; 0.4 h)
  other      79.7 /  112.4 /  182.0 s (10; 0.2 h)
  compact   102.1 /  112.2 /  120.5 s (8; 0.2 h)
chat wait, any moment of the run: p50 48 s, p90 145 s, over 60 s 42 %
chat wait, while a call is in flight (10-18 basis): p50 50 s, p90 147 s, over 60 s 43 %
```
