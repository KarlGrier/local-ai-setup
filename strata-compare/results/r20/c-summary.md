# C (2026-10-14): the 7 stuck coding answers - quant or engine?

Continued from the same cut (the original reasoning + the withheld 256th digit), repeat limit 1024 in total, the original
sampling (T 1.0, top_p 0.95, top_k 20, min_p 0.05). Digit counts include the original's 255 visible + the withheld 256th.

| case | IQ3_S cont (10-13) | Q8_0 cont | IQ3_S + presence 0.5 |
|---|---|---|---|
| c171-iq3s-full:c02_rle:2 | 1023 (looped) | 1023 (looped) | 1023 (looped) |
| c171-iq3s-full:c16_json_parser:0 | 1023 (looped) | 1023 (looped) | 1023 (looped) |
| c171-iq3s-full:c23_refactor_orderbook:2 | 1023 (looped) | 1023 (looped) | 1023 (looped) |
| c171-iq3s-quick:c07_rpn:0 | 1023 (looped) | 1023 (looped) | 1023 (looped) |
| c171-iq3s-quick:c16_json_parser:0 | 1023 (looped) | 1023 (looped) | 1023 (looped) |
| r16-q4-quick:c14_semver:0 | 1023 (looped) | 1023 (looped) | 1023 (looped) |
| r16-q4-quick:c16_json_parser:0 | 1023 (looped) | 1023 (looped) | 1023 (looped) |

**0 of 7 broke out on Q8_0; 0 of 7 with presence_penalty 0.5 on IQ3_S.**

Top token's probability inside the run (teacher-forced, STRATA_LOGPOS; llama.cpp = the signal-3.8-opus build 6fcaa16 on
the same Q8_0 file and the same token ids). Digit 300 / 600 / 900:

| case | Strata IQ3_S | Strata Q8_0 | llama.cpp Q8_0 | lowest p(top) after digit 256 (IQ3_S / Q8_0) |
|---|---|---|---|---|
| c171-iq3s-full:c02_rle:2 | 0.9970 / 0.9994 / 0.9994 | 0.9971 / 0.9995 / 0.9992 | 0.9979 / 0.9997 / 0.9994 | 0.963 at 505 / 0.889 at 507 |
| c171-iq3s-full:c16_json_parser:0 | 0.9982 / 0.9990 / 0.9989 | 0.9987 / 0.9992 / 0.9996 | - | 0.989 at 309 / 0.972 at 506 |
| c171-iq3s-full:c23_refactor_orderbook:2 | 0.9962 / 0.9963 / 0.9978 | 0.9977 / 0.9997 / 0.9975 | 0.9980 / 0.9976 / 0.9981 | 0.938 at 509 / 0.953 at 509 |
| c171-iq3s-quick:c07_rpn:0 | 0.9956 / 0.9976 / 0.9967 | 0.9983 / 0.9987 / 0.9958 | 0.9958 / 0.9976 / 0.9960 | 0.925 at 509 / 0.954 at 509 |
| c171-iq3s-quick:c16_json_parser:0 | 0.9962 / 0.9996 / 0.9984 | 0.9937 / 0.9996 / 0.9989 | - | 0.980 at 384 / (online only) |
| r16-q4-quick:c14_semver:0 | 0.9950 / 0.9975 / 0.9985 | 0.9977 / 0.9993 / 0.9990 | - | 0.962 at 520 / 0.936 at 505 |
| r16-q4-quick:c16_json_parser:0 | 0.9974 / 0.9980 / 0.9997 | 0.9956 / 0.9991 / 0.9998 | - | 0.954 at 267 / (online only) |
