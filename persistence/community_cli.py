"""Operator-only private-log erasure, separate from public community endpoints."""
from __future__ import annotations

import json
import sys

from persistence import community


def delete_chat(args) -> None:
    try:
        result = (community.delete_chat_message(args.evidence_ref)
                  if args.chat_action == "delete" else community.delete_tester_chat(args.tester))
    except community.CommunityError:
        print(json.dumps({"error": "The private chat deletion was refused."}), file=sys.stderr)
        raise SystemExit(1) from None
    except community.CommunityUnavailable:
        print(json.dumps({"error": "Private chat records are unavailable."}), file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
