#!/bin/bash
# hostcheck.sh — round 10 (v0.1.38's DNS-rebinding Host check, server bound to 127.0.0.1:8081, run inside with_server):
# the answer to /health with the Host headers a local client, an IP, a Docker client and a rebinding page would send.
for h in "127.0.0.1:8081" "localhost:8081" "192.168.1.10:8081" "host.docker.internal:8081" "rebind.example.com:8081"; do
  printf '%-28s -> HTTP %s\n' "$h" "$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $h" http://127.0.0.1:8081/health)"
done
printf '%-28s -> HTTP %s\n' "Origin: https://evil.example" "$(curl -s -o /dev/null -w '%{http_code}' -H 'Origin: https://evil.example' -H 'Content-Type: application/json' -d '{"model":"x","messages":[{"role":"user","content":"hi"}],"max_tokens":4}' http://127.0.0.1:8081/v1/chat/completions)"
printf '%-28s -> HTTP %s\n' "no Origin (curl / SDKs)" "$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{"model":"x","messages":[{"role":"user","content":"hi"}],"max_tokens":4}' http://127.0.0.1:8081/v1/chat/completions)"
