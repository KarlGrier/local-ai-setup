"""Runs inside the sandbox: imports the model's solution.py and runs each test_* function of hidden_test.py
(each test gets the solution module as its argument).  One result line per test, prefixed with a nonce."""
import json
import signal
import sys

sys.path.insert(0, "/work")
sys.setrecursionlimit(20000)
NONCE = sys.argv[1]
PER_TEST = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0


def emit(d):
    sys.__stdout__.write(NONCE + json.dumps(d) + "\n")
    sys.__stdout__.flush()


class Timeout(BaseException):
    pass


def on_alarm(sig, frame):
    raise Timeout()


signal.signal(signal.SIGALRM, on_alarm)
import hidden_test as T                     # noqa: E402  (the checker's own file)
tests = [(n, f) for n, f in vars(T).items() if n.startswith("test_") and callable(f)]
emit({"total": len(tests)})
try:
    signal.setitimer(signal.ITIMER_REAL, 20.0)
    import solution                          # noqa: E402  (the model's code)
    signal.setitimer(signal.ITIMER_REAL, 0)
except BaseException as e:                   # noqa: BLE001
    signal.setitimer(signal.ITIMER_REAL, 0)
    emit({"import_error": (type(e).__name__ + ": " + str(e))[:400]})
    sys.exit(0)
for name, fn in tests:
    signal.setitimer(signal.ITIMER_REAL, PER_TEST)
    try:
        fn(solution)
        ok, msg = True, ""
    except Timeout:
        ok, msg = False, "timeout"
    except BaseException as e:               # noqa: BLE001  (SystemExit from model code counts as a failure)
        ok, msg = False, (type(e).__name__ + ": " + str(e))[:300]
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    emit({"test": name, "ok": ok, "msg": msg})
emit({"done": True})
