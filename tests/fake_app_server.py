"""A scripted stand-in for ``codex app-server`` (JSON-RPC over stdio).

The scenario comes from ``FAKE_SCENARIO``; see the tests in ``test_transport_lifecycle.py``.
"""

import json
import os
import subprocess
import sys


out = sys.stdout.buffer
scenario = os.environ.get("FAKE_SCENARIO", "")
THREAD = "thread-1"
TURN = "turn-1"


def send(*messages: dict) -> None:
    """Write all messages in one write (the client sees them buffered together)."""
    out.write(b"".join((json.dumps(m) + "\n").encode() for m in messages))
    out.flush()


def turn(status: str) -> dict:
    return {"id": TURN, "items": [], "status": status}


if scenario == "garbage":
    out.write(b"WARN: not json\n\xff\xfe not utf-8\n[1, 2]\n")
    out.flush()
if scenario == "stderr_flood":
    chunk = "x" * 1023 + "\n"
    for _ in range(25 * 1024):  # 25 MB
        sys.stderr.write(chunk)
    sys.stderr.flush()
if scenario == "child":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    with open(os.environ["CHILD_PID_FILE"], "w") as f:  # noqa: PTH123
        f.write(str(child.pid))

interrupts: list[dict] = []
for line in sys.stdin:
    msg = json.loads(line)
    method = msg.get("method")
    if method is None:  # a response to our server request
        continue
    req_id = msg["id"]
    if method == "initialize":
        send({"jsonrpc": "2.0", "id": req_id, "result": {}})
        if scenario == "server_request":
            send({"jsonrpc": "2.0", "id": "srv-1", "method": "test/ask", "params": {}})
    elif method == "die":
        sys.stderr.write("panic: something broke\n")
        sys.stderr.flush()
        sys.exit(3)
    elif method == "turn/start" and scenario == "slow_turn":  # runs until interrupted
        send(
            {"jsonrpc": "2.0", "id": req_id, "result": {"turn": turn("inProgress")}},
            {"method": "turn/started", "params": {"threadId": THREAD, "turn": turn("inProgress")}},
        )
    elif method == "turn/interrupt":
        interrupts.append(msg["params"])
        send({"jsonrpc": "2.0", "id": req_id, "result": {}})
    elif method == "fake/interrupts":
        send({"jsonrpc": "2.0", "id": req_id, "result": {"interrupts": interrupts}})
    elif method == "turn/start":
        send(
            {"jsonrpc": "2.0", "id": req_id, "result": {"turn": turn("inProgress")}},
            {"method": "turn/started", "params": {"threadId": THREAD, "turn": turn("inProgress")}},
            {"method": "turn/completed", "params": {"threadId": THREAD, "turn": turn("completed")}},
        )
    elif method == "turn/start-then-die":
        send({"jsonrpc": "2.0", "id": req_id, "result": {"turn": turn("inProgress")}})
        sys.exit(1)
    else:
        send({"jsonrpc": "2.0", "id": req_id, "result": {"echo": method}})
