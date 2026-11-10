# offline-env.sh - sourced by the usability launchers (configs/usability/bin/*).
# Everything bound for the internet goes to the refusing proxy on 127.0.0.1:18999 (configs/usability/bin/denyproxy.py
# logs what was asked and answers 403; when it is not running the connection is simply refused). Loopback stays direct,
# so Strata (127.0.0.1:8080) and SearXNG (127.0.0.1:8888) work. Both spellings: curl reads only the lowercase ones.
P=http://127.0.0.1:18999
export HTTP_PROXY=$P HTTPS_PROXY=$P ALL_PROXY=$P http_proxy=$P https_proxy=$P all_proxy=$P
export NO_PROXY=localhost,127.0.0.1,::1 no_proxy=localhost,127.0.0.1,::1
export NODE_USE_ENV_PROXY=1           # Node 24's own fetch follows the variables only with this
unset P
