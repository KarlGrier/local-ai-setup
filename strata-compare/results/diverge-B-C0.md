| prompt | B tokens | C0 tokens | identical | first divergence (token index) | context at divergence |
|---|---|---|---|---|---|
| arith | 86 | 85 | no | 35 | '/12=12. Sum' → '=40' vs ' 40' |
| code | 350 | 328 | no | 43 | ' provide code likely. Need final concise but' → ' complete. Need' vs ' enough. Ensure' |
| network | 356 | 356 | yes | none |  |
| science | 185 | 252 | no | 46 | ' Could say: Sunlight contains all colors' → ', and molecules' vs '; shorter blue' |
| translate | 266 | 253 | no | 160 | 'achmittag. "has been moved"' → ' passive perfect:' vs ' = wurde versch' |
