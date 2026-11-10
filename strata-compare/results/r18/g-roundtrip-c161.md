### round trip, tags c161-*

| case | comparison | tokens | argmax changed (first at) | NLL identical | max abs ΔNLL | mean ΔNLL | drafter guesses changed | state hash: same / different | prompt (tokens, reused, read) a vs b |
|---|---|---|---|---|---|---|---|---|---|
| small | direct vs direct (residual) | 1536 | 0 (None) | 1536 | 0.00e+00 | +0.00e+00 | 183 of 385 | – / – | [['5822', '5726', '96']] vs [['5822', '5726', '96']] |
| small | parked → resumed vs direct | 1536 | 0 (None) | 1536 | 0.00e+00 | +0.00e+00 | 189 of 385 | – / – | [['5822', '5726', '96']] vs [['5822', '5726', '96']] |
| small | resumed + edit vs edit read directly | 1536 | 0 (None) | 1536 | 0.00e+00 | +0.00e+00 | 186 of 385 | – / – | [['5826', '2579', '3247']] vs [['5826', '2579', '3247']] |
| 40k | direct vs direct (residual) | – | (missing) | | | | | | |
| 40k | parked → resumed vs direct | – | (missing) | | | | | | |
| 40k | resumed + edit vs edit read directly | – | (missing) | | | | | | |
