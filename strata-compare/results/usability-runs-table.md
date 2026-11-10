| task | harness | run | green | steps | output tok | wall s | prompt tok re-read (total / median per turn / max) | model s | largest prompt | tool calls | unparsed calls | bad args | early ends | side requests |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| a1_inventory | opencode | r1 | yes | 15 | 3,481 | 34 | 9,058 / 239 / 5,220 | 33 | 12,208 | 14 | 0 | 0 | 0 | 0 |
| a1_inventory | codex | r1 | yes | 7 | 3,031 | 29 | 12,616 / 252 / 9,019 | 28 | 15,248 | 7 | 0 | 0 | 0 | 0 |
| a1_inventory | dsh-minimal | r1 | yes | 8 | 4,193 | 72 | 3,404 / 270 / 1,905 | 34 | 7,830 | 9 | 0 | 0 | 0 | 0 |
| a1_inventory | dsh-standard | r1 | yes | 15 | 3,997 | 72 | 11,231 / 248 / 6,688 | 39 | 14,769 | 14 | 0 | 0 | 0 | 0 |
| a1_inventory | dsh-standard | r2 | yes | 9 | 3,843 | 72 | 10,839 / 572 / 6,688 | 35 | 13,966 | 14 | 0 | 0 | 0 | 0 |
| a1_inventory | dsh-ptc | r1 | yes | 8 | 3,217 | 66 | 12,609 / 705 / 7,794 | 30 | 15,276 | 7 | 0 | 0 | 0 | 0 |
| a2_textstats | opencode | r1 | yes | 8 | 4,548 | 39 | 10,822 / 882 / 5,222 | 38 | 12,632 | 13 | 0 | 0 | 0 | 0 |
| a2_textstats | codex | r1 | yes | 11 | 6,272 | 54 | 13,875 / 218 / 9,028 | 53 | 19,778 | 12 | 0 | 0 | 0 | 0 |
| a2_textstats | dsh-minimal | r1 | yes | 17 | 12,246 | 147 | 11,488 / 186 / 6,929 | 98 | 16,797 | 18 | 0 | 0 | 0 | 0 |
| a2_textstats | dsh-standard | r1 | yes | 22 | 38,688 | 357 | 119,522 / 556 / 28,215 | 317 | 34,671 | 18 | 0 | 0 | 0 | 0 |
| a2_textstats | dsh-standard | r2 | yes | 10 | 5,757 | 82 | 14,351 / 654 / 6,690 | 48 | 16,018 | 13 | 0 | 0 | 0 | 0 |
| a2_textstats | dsh-ptc | r1 | yes | 11 | 7,800 | 102 | 15,736 / 415 / 7,796 | 65 | 19,334 | 10 | 0 | 0 | 0 | 0 |
| a3_cronlite | opencode | r1 | yes | 9 | 7,850 | 64 | 13,535 / 173 / 5,224 | 62 | 16,124 | 13 | 0 | 0 | 0 | 0 |
| a3_cronlite | codex | r1 | yes | 10 | 11,120 | 92 | 16,563 / 1,112 / 9,037 | 88 | 27,062 | 12 | 0 | 0 | 0 | 0 |
| a3_cronlite | dsh-minimal | r1 | yes | 19 | 15,494 | 162 | 10,137 / 346 / 1,839 | 121 | 25,730 | 21 | 0 | 0 | 0 | 0 |
| a3_cronlite | dsh-standard | r1 | yes | 26 | 32,248 | 322 | 102,743 / 504 / 26,874 | 259 | 33,331 | 22 | 0 | 0 | 0 | 0 |
| a3_cronlite | dsh-standard | r2 | yes | 17 | 12,373 | 142 | 11,353 / 210 / 6,692 | 97 | 23,130 | 16 | 0 | 0 | 0 | 0 |
| a3_cronlite | dsh-ptc | r1 | yes | 13 | 10,286 | 122 | 13,471 / 286 / 7,798 | 83 | 23,278 | 12 | 0 | 0 | 0 | 0 |
| rt_effort | opencode | r1 | no (hidden fail, suite fail) | 16 | 9,552 | 84 | 39,786 / 2,349 / 6,068 | 83 | 45,727 | 22 | 2 | 0 | 0 | 0 |
| rt_effort | opencode | r2 | yes | 20 | 11,804 | 106 | 50,175 / 2,359 / 6,068 | 105 | 57,703 | 32 | 1 | 0 | 0 | 0 |
| rt_effort | codex | r1 | yes | 36 | 16,938 | 155 | 48,952 / 1,250 / 9,879 | 153 | 62,517 | 42 | 1 | 0 | 0 | 0 |
| rt_effort | codex | r2 | no (hidden fail, suite fail) | 16 | 9,732 | 87 | 44,771 / 2,442 / 9,879 | 86 | 50,758 | 30 | 0 | 0 | 0 | 0 |
| rt_effort | dsh-minimal | r1 | yes | 20 | 12,807 | 146 | 35,351 / 1,692 / 4,911 | 110 | 45,976 | 30 | 1 | 0 | 0 | 0 |
| rt_effort | dsh-minimal | r2 | yes | 27 | 11,293 | 146 | 48,906 / 1,748 / 3,398 | 107 | 58,673 | 43 | 1 | 0 | 0 | 0 |
| rt_effort | dsh-standard | r1 | yes | 45 | 19,274 | 227 | 49,270 / 839 / 7,561 | 178 | 67,456 | 53 | 0 | 0 | 0 | 0 |
| rt_effort | dsh-standard | r2 | no (hidden fail, suite fail) | 40 | 26,203 | 267 | 53,812 / 864 / 7,561 | 228 | 71,961 | 53 | 1 | 0 | 0 | 0 |
| rt_effort | dsh-ptc | r1 | yes | 38 | 23,868 | 257 | 67,138 / 1,083 / 8,667 | 215 | 85,386 | 40 | 1 | 0 | 0 | 0 |

Totals per harness (all tasks in these tags):
- opencode: green 4/5, steps 68, output tokens 37,235, wall 326 s (model 321 s), re-read 123,376, unparsed 3, bad args 0, early ends 0
- codex: green 4/5, steps 80, output tokens 47,093, wall 417 s (model 408 s), re-read 136,777, unparsed 1, bad args 0, early ends 0
- dsh-minimal: green 5/5, steps 91, output tokens 56,033, wall 673 s (model 470 s), re-read 109,286, unparsed 2, bad args 0, early ends 0
- dsh-standard: green 7/8, steps 184, output tokens 142,383, wall 1538 s (model 1200 s), re-read 373,121, unparsed 1, bad args 0, early ends 0
- dsh-ptc: green 4/4, steps 70, output tokens 45,171, wall 546 s (model 393 s), re-read 108,954, unparsed 1, bad args 0, early ends 0
