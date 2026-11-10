| case | comparison | tokens | argmax changed (first at) | NLL identical | max abs ΔNLL | mean ΔNLL | drafter guesses changed | state hash: same / different | prompt (tokens, reused, read) a vs b |
|---|---|---|---|---|---|---|---|---|---|
| small | direct vs direct (residual) | 1536 | 0 (None) | 1536 | 0.00e+00 | +0.00e+00 | 0 of 385 | L,gdn,ple,tail,pooled,kv,mtp,stale,ple_prev / – | [['5822', '5726', '96']] vs [['5822', '5726', '96']] |
| small | parked → resumed vs direct | 1536 | 30 (39) | 39 | 2.80e-01 | -1.25e-03 | 376 of 385 | L,ple_prev / gdn,ple,tail,pooled,kv,mtp,stale | [['5822', '5726', '96']] vs [['5822', '5726', '96']] |
| small | resumed + edit vs edit read directly | 1536 | 30 (44) | 47 | 3.81e-01 | -3.03e-03 | 373 of 385 | L,ple_prev / gdn,ple,tail,pooled,kv,mtp,stale | [['5826', '2579', '3247']] vs [['5826', '2579', '3247']] |
| 40k | direct vs direct (residual) | – | (missing) | | | | | | |
| 40k | parked → resumed vs direct | – | (missing) | | | | | | |
| 40k | resumed + edit vs edit read directly | – | (missing) | | | | | | |
