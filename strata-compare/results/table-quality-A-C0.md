| prompt | check | A | C0 |
|---|---|---|---|
| 01_security_incident | VPN 08:04:45 (UTC-5 conversion) | ✔ | ✔ |
| 01_security_incident | log clear 08:24 | ✔ | ✔ |
| 01_security_incident | E09 described as failed/attempted (not a successful lateral move) | ✔ | ✔ |
| 01_security_incident | E08 treated as data (mentions it / injection) | ✔ | ✔ |
| 01_security_incident | svc_ops credential action | ✔ | ✔ |
| 01_security_incident | says exfiltration is NOT established | ✔ | ✔ |
| 01_security_incident | (generated, finish) | 30202 tok, stop | 26516 tok, stop |
| 02_network_troubleshooting | gateway 192.168.10.1 | ✔ | ✘ |
| 02_network_troubleshooting | trunk allowed vlan add 20 | ✔ | ✘ |
| 02_network_troubleshooting | ACL: host exception ordered before the VLAN-10 deny | ✔ | ✘ |
| 02_network_troubleshooting | keeps restriction (does not just delete deny 10) | ✔ | ✔ |
| 02_network_troubleshooting | no static route needed | ✔ | ✘ |
| 02_network_troubleshooting | (generated, finish) | 25891 tok, stop | 32768 tok, length |
| 03_ccna_tutor | broadcast .63 | ✔ | ✔ |
| 03_ccna_tutor | server subnet .64/26 network address | ✔ | ✔ |
| 03_ccna_tutor | /30 two usable hosts | ✔ | ✔ |
| 03_ccna_tutor | TTL decremented | ✔ | ✔ |
| 03_ccna_tutor | TCP is Layer 4 / transport | ✔ | ✔ |
| 03_ccna_tutor | five quiz questions | ✔ | ✔ |
| 03_ccna_tutor | (generated, finish) | 10434 tok, stop | 15943 tok, stop |
| 04_local_ai_performance | A W1 252.5 | ✔ | ✔ |
| 04_local_ai_performance | B W1 189.27 | ✔ | ✔ |
| 04_local_ai_performance | C W1 181.29 | ✔ | ✔ |
| 04_local_ai_performance | D W3 427.94 | ✔ | ✔ |
| 04_local_ai_performance | break-even N ~2905 | ✔ | ✔ |
| 04_local_ai_performance | actual task B ~281.6 | ✔ | ✔ |
| 04_local_ai_performance | actual task C ~188.07 | ✔ | ✔ |
| 04_local_ai_performance | (generated, finish) | 32768 tok, length | 22997 tok, stop |
| 05_patch_policy_constraints | eligible == [D04, L01, L09, L11] | ✔ | ✔ |
| 05_patch_policy_constraints | 200 Mbps | ✔ | ✔ |
| 05_patch_policy_constraints | 25 MB/s | ✔ | ✔ |
| 05_patch_policy_constraints | 320 s | ✔ | ✔ |
| 05_patch_policy_constraints | no forced reboot while logged in | ✔ | ✔ |
| 05_patch_policy_constraints | (generated, finish) | 8202 tok, stop | 16580 tok, stop |
| **total** | | 29/29 | 25/29 |
