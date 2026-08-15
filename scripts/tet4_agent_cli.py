"""CLI nhẹ cho bước brainstorm của Tet4 agent-first, không nạp Qwen/GPU."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.tet4_agent import Tet4Agent


def main() -> None:
    parser = argparse.ArgumentParser(description="Tet4 agent: brainstorm rồi chờ người dùng chọn keyword")
    parser.add_argument("wish_intent", help="Ý chúc người dùng muốn gửi")
    parser.add_argument("--keywords", nargs="+", help="Đúng 2 hoặc 3 keyword để xuất prompt lập plan")
    parser.add_argument("--corpus", type=Path, default=None)
    args = parser.parse_args()
    agent = Tet4Agent(args.corpus) if args.corpus else Tet4Agent()
    brief = agent.brainstorm(args.wish_intent)
    if not args.keywords:
        print(json.dumps({"stage": "awaiting_keyword_selection", "creative_brief": brief.to_dict()}, ensure_ascii=False, indent=2))
        return
    metadata = agent.select_keywords(args.wish_intent, args.keywords)
    print(json.dumps({"stage": "ready_for_planning", "metadata": metadata,
                      "plan_messages": agent.build_plan_messages(brief, metadata)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
