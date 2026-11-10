### round trip, tags r16-acc-c16-*

| case | comparison | tokens | argmax changed (first at) | NLL identical | max abs ΔNLL | mean ΔNLL | drafter guesses changed | state hash: same / different | prompt (tokens, reused, read) a vs b |
|---|---|---|---|---|---|---|---|---|---|
| small | direct vs direct (residual) | 1536 | 31 (128) | 56 | 3.86e-01 | -9.50e-04 | 369 of 385 | L,ple,stale,dead,ple_prev / gdn,tail,pooled,kv,mtp,pooled_full | [['5822', '5726', '96']] vs [['5822', '5726', '96']] |
| small | parked → resumed vs direct | 1536 | 32 (124) | 53 | 4.31e-01 | +1.32e-03 | 373 of 385 | L,ple,dead,ple_prev / gdn,tail,pooled,kv,mtp,stale,pooled_full | [['5822', '5726', '96']] vs [['5822', '5726', '96']] |
| small | resumed + edit vs edit read directly | 1536 | 0 (None) | 1536 | 0.00e+00 | +0.00e+00 | 191 of 385 | L,gdn,ple,tail,pooled,kv,mtp,dead,pooled_full,ple_prev / stale | [['5826', '2579', '3247']] vs [['5826', '2579', '3247']] |
| 40k | direct vs direct (residual) | – | (missing) | | | | | | |
| 40k | parked → resumed vs direct | – | (missing) | | | | | | |
| 40k | resumed + edit vs edit read directly | – | (missing) | | | | | | |
