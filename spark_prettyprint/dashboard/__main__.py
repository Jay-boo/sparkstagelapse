from __future__ import annotations

import argparse
import os
import signal

import requests

from .server import DEFAULT_HOST, DEFAULT_PORT, pid_file, run


def _status(host: str, port: int) -> None:
    try:
        r = requests.get(f"http://{host}:{port}/health", timeout=0.5)
        if r.ok:
            print(f"running (pid={r.json().get('pid')}) at http://{host}:{port}")
        else:
            print(f"got HTTP {r.status_code} from http://{host}:{port}")
    except Exception:
        print(f"not running on http://{host}:{port}")


def _stop(port: int) -> None:
    pf = pid_file(port)
    if not pf.exists():
        print("no pid file found — is the server running?")
        return
    pid = int(pf.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"sent SIGTERM to pid {pid}")
    except ProcessLookupError:
        print("process already gone")
    finally:
        pf.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m spark_prettyprint.dashboard")
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    if args.action == "start":
        # Démarrage manuel, EN PREMIER PLAN (bloquant). Pour un démarrage
        # automatique et détaché, utilisez simplement DashboardClient.push()
        # depuis votre script, qui spawn le serveur lui-même si besoin.
        run(host=args.host, port=args.port)
    elif args.action == "stop":
        _stop(args.port)
    elif args.action == "status":
        _status(args.host, args.port)


if __name__ == "__main__":
    main()
