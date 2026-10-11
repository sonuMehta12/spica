"""
Help for the person reading the replies — Claude, after each run. Nothing here
grades: it lays a run out to be read, and points at the replies most worth
reading first (spec/done/chat-quality.md § The harness).

    uv run python -m evals.judge_aid                 # the latest report
    uv run python -m evals.judge_aid reports/n2n-….json --all

A reply is flagged when it carries a number found in none of: the tool results
as the model read them, the turn's context block, or the person's own words.
A flag is a pointer, not a verdict — a date or a count can be a fair reading.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
_NUM = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")


def context_of(model_input) -> str:
    """The context block on the person's message: everything before the
    sentence they said."""
    if isinstance(model_input, list):
        for item in reversed(model_input):
            if isinstance(item, dict) and item.get("role") == "user":
                c = item.get("content")
                if isinstance(c, str):
                    return c.rsplit("\n\n", 1)[0]
    return ""


def _nums(s: str) -> set[str]:
    out = set()
    for m in _NUM.findall(s or ""):
        n = m.replace(",", "")
        out.add(n.rstrip("0").rstrip(".") if "." in n else n)
    return out


def unbacked(run: dict, said: str) -> list[str]:
    """Numbers in the reply that appear nowhere it could have read them."""
    from app.agent.tools import for_model
    seen = json.dumps([for_model(t["tool"], t.get("result")) for t in run.get("tools", [])],
                      ensure_ascii=False, default=str)
    pool = _nums(seen) | _nums(run.get("context", "")) | _nums(said) | _nums(
        " ".join(e.get("said", "") + " " + e.get("reply", "") for e in run.get("earlier", [])))
    return sorted(n for n in _nums(run.get("reply", "")) if n not in pool and len(n) > 1)


def main() -> None:
    import os
    sys.path.insert(0, str(HERE.parent))
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://cortex:cortex@localhost:5434/cortex_eval")
    from app.agent.tools import for_model

    reports = HERE / "reports"
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = Path(args[0]) if args else max(reports.glob("n2n-*.json"))
    show_all = "--all" in sys.argv
    r = json.loads(path.read_text())
    print(f"{path.name}: {r['model']} effort {r.get('effort')} · {r['passed']}/{r['cases_n']} "
          f"cases · {r.get('turns_passed')}/{r.get('turns')} turns\n")
    for c in r["cases"]:
        for i, run in enumerate(c["runs"]):
            flags = unbacked(run, c["say"])
            if not show_all and run.get("passed") and not flags:
                continue
            mark = "✓" if run.get("passed") else "✗"
            print(f"{mark} {c['id']} · day {i + 1} · {run.get('at')} · “{c['say']}”")
            print(f"   reply: {run.get('reply', '')[:400]}")
            for t in run.get("tools", []):
                res = json.dumps(for_model(t["tool"], t.get("result")), ensure_ascii=False,
                                 default=str)
                print(f"   {'·' if t.get('ok') else '✕'} {t['tool']}"
                      f"({json.dumps(t.get('args'), ensure_ascii=False)[:160]}) → {res[:240]}")
            if run.get("cards"):
                print(f"   cards: {[x.split(' — ')[0] for x in run['cards']]}")
            for f in run.get("failures", []):
                print(f"   ✗ {f[:220]}")
            if flags:
                print(f"   ? numbers not in anything it read: {flags}")
            print()


if __name__ == "__main__":
    main()
