"""Protected Gmail gateway; --outbox is compatible with the fixed PM hook.

Deploy this script and its imported services in a fixed, hash-checked external
runtime. Pass --config explicitly, or place automation_mail.config.json beside
the external script. An in-repository config is refused. No auth is inherited
from the chat connector, browser, environment or developer AI profile.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from contextlib import suppress
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.automation.mail_broker import MailBroker, MailError, _json


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).with_suffix(".config.json"))
    parser.add_argument("command", nargs="?", choices=("send", "poll", "observe", "preflight"))
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--outbox", type=Path, help="deliver/reconcile one exact recorded PM action")
    operation.add_argument("--preflight", action="store_true", help="check exact authenticated sender; no mail sent")
    operation.add_argument("--observe", action="store_true", help="read immutable report-only events; no network or publication")
    operation.add_argument("--once", action="store_true", help="one reply poll; never sends an unrequested outbox")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args(argv)
    transport = None
    try:
        if not 30 <= args.interval <= 300:
            raise MailError("bounded mail poll interval required")
        if args.command == "send" and not args.outbox:
            raise MailError("send needs one exact PM outbox")
        if args.command in {"poll", "observe", "preflight"} and args.outbox:
            raise MailError("read/poll commands cannot send an outbox")
        config = _json(args.config, 65536)
        if config.get("transport", "gmail_rest") == "codex_appserver":
            from services.automation.mail_connector import CodexGmailTransport

            transport = CodexGmailTransport(executable=config["codex_executable"],
                                           workspace=config["connector_workspace"], timeout_seconds=60)
        elif config.get("transport", "gmail_rest") != "gmail_rest":
            raise MailError("mail transport must select the fixed connector or narrow REST client")
        broker = MailBroker(config, gmail=transport)
        if args.outbox:
            print(json.dumps(broker.deliver(args.outbox), ensure_ascii=False), flush=True)
            return 0
        if args.preflight or args.command == "preflight":
            print(json.dumps(broker.preflight(), ensure_ascii=False), flush=True)
            return 0
        if args.observe or args.command == "observe":
            print(json.dumps({"events": broker.observation_events()}, ensure_ascii=False), flush=True)
            return 0
        while True:
            print(json.dumps(broker.poll_replies(), ensure_ascii=False), flush=True)
            if args.once:
                return 0
            time.sleep(args.interval)
    except (MailError, ValueError, OSError, KeyError, TypeError, RuntimeError):
        print(json.dumps({"status": "unconfigured_or_refused", "verified_sent": False,
                          "reason": "mail authentication/configuration/evidence needs operator verification"}), file=sys.stderr)
        return 1
    finally:
        if transport:
            with suppress(Exception):
                transport.close()


if __name__ == "__main__":
    raise SystemExit(main())
