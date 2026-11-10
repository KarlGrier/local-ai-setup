# C's greedy divergence on G-P4K0 through the SERVED path: a near-tie within rounding?

Rule: tie/rule.txt (tie_check.py's, unchanged: the frozen 11-05 text, byte for byte); where: tie/where.txt.
11-05 (command line, results/ds41/gate-1105-2032-csample): C1f did not leave C0f within 512 tokens - no verdict.

Verdict: **within rounding - C is not disqualified (its speed arms run under sampling)**

- first divergent generated token j = 33 (served texts this gap: char 126; 11-04: char 126): C0f ' text' vs C1f ' terms'
- C1f's served G-P4K0 text = 11-04's: True
- C0f's served G-P4K0 text = 11-04's: True; its served ids = 11-05's command-line ids: True
- rule: gap <= 0.5883 nats, the p90 (rule.txt; Karl 11-04); C0f's own gap (window 1): 0.018874000000000057
- under the maximum (4.3312 nats, reported only): within
- window 1 reproduces C0f's path at every position before j: True
- w1: top-1 ' text'; logprob C0f's token -1.1963, C1f's -1.2152, gap 0.0189; top-5 ' text' -1.196, ' terms' -1.215, ',' -1.719, ' legal' -2.077, ' —' -3.052
- w2a: top-1 ' text'; logprob C0f's token -1.1963, C1f's -1.2152, gap 0.0189; top-5 ' text' -1.196, ' terms' -1.215, ',' -1.719, ' legal' -2.077, ' —' -3.052
- w2b: top-1 ' text'; logprob C0f's token -0.7630, C1f's -1.4815, gap 0.7185; top-5 ' text' -0.763, ' terms' -1.481, ',' -2.031, ' legal' -2.292, ' —' -3.271

| generated token | target | top-1 = target | top-2 gap (nats) |
|---|---|---|---|
| 1 | ' Technical' | True | 2.5365 |
| 2 | ' Summary' | True | 8.3831 |
| 3 | '\n\n' | True | 2.3672 |
| 4 | '##' | True | 0.5022 |
| 5 | ' ' | True | 1.4582 |
| 6 | '1' | True | 9.2168 |
| 7 | '.' | True | 6.8284 |
| 8 | ' Apache' | True | 1.7664 |
| 9 | ' License' | True | 10.9895 |
| 10 | ' ' | True | 2.3486 |
| 11 | '2' | True | 15.1039 |
| 12 | '.' | True | 16.1115 |
| 13 | '0' | True | 15.8291 |
| 14 | ' (' | True | 0.1942 |
| 15 | 'License' | True | 0.7531 |
| 16 | ' Text' | True | 3.6064 |
| 17 | ')\n\n' | True | 2.1647 |
| 18 | '**' | True | 4.8669 |
| 19 | 'Purpose' | True | 7.8556 |
| 20 | ':**' | True | 5.6617 |
| 21 | ' This' | True | 0.0233 |
| 22 | ' is' | True | 5.8707 |
| 23 | ' the' | True | 4.5505 |
| 24 | ' standard' | True | 1.5432 |
| 25 | ' Apache' | True | 6.3404 |
| 26 | ' License' | True | 2.7473 |
| 27 | ',' | True | 5.3030 |
| 28 | ' Version' | True | 10.6290 |
| 29 | ' ' | True | 15.2505 |
| 30 | '2' | True | 15.5514 |
| 31 | '.' | True | 18.0979 |
| 32 | '0' | True | 15.9443 |
| 33 | ' text' | True | 0.0189 |
