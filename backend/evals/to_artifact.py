"""
A run's report, shaped for the review page — the Card test run artifact's Eval
view.

    uv run python -m evals.to_artifact                      # the latest report
    uv run python -m evals.to_artifact reports/n2n-….json   # a chosen one

Writes one JSON file per case to `reports/artifact/eval/` and one for the run
to `reports/artifact/evalruns/`, each the document the page reads from its
store. Claude sends them with the artifact's data tool; nothing here talks to
the artifact itself. Tool results are cut to what a person reads in review —
the full ones stay in the report.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from evals.cases import CASES, ONBOARDING

HERE = Path(__file__).resolve().parent
RESULT_CHARS = 1500
ARGS_CHARS = 400


def _cut(value, n: int) -> str:
    s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return s if len(s) <= n else s[: n - 1] + "…"


def main() -> None:
    reports = HERE / "reports"
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else max(reports.glob("n2n-*.json"))
    report = json.loads(path.read_text())
    out = reports / "artifact"
    shutil.rmtree(out, ignore_errors=True)
    (out / "eval").mkdir(parents=True)
    (out / "evalruns").mkdir(parents=True)
    order = {c.id: i for i, c in enumerate([*CASES, *ONBOARDING])}

    for i, c in enumerate(report["cases"]):
        runs = [{
            "passed": r["passed"], "failures": r["failures"], "reply": r.get("reply", ""),
            "cards": r.get("cards", []), "earlier": r.get("earlier", []),
            "judge": r.get("judge"), "seconds": r.get("seconds"),
            "tools": [{"tool": t["tool"], "ok": t.get("ok"), "error": t.get("error"),
                       "args": _cut(t.get("args") or {}, ARGS_CHARS),
                       "result": _cut(t.get("result"), RESULT_CHARS)}
                      for t in r.get("tools", [])],
        } for r in c["runs"]]
        doc = {
            "id": c["id"], "order": order.get(c["id"], 1000 + i), "group": c["group"],
            "say": c["say"], "given": c.get("given", []), "why": c.get("why", ""),
            "known": c.get("known"), "expect": c.get("expect", []), "must": c.get("must", []),
            "must_not": c.get("must_not", []), "passes": c["passes"], "n": len(runs),
            "run": report["id"], "model": report["model"], "runs": runs,
        }
        (out / "eval" / f"{c['id']}.json").write_text(json.dumps(doc, ensure_ascii=False))

    run = {k: report.get(k) for k in ("id", "model", "judge", "today", "repeat", "cases_n",
                                       "passed", "failed", "known", "seconds", "by_group",
                                       "tokens_in", "tokens_out", "judge_tokens_in",
                                       "judge_tokens_out")}
    (out / "evalruns" / f"{report['id']}.json").write_text(json.dumps(run, ensure_ascii=False))
    sizes = sorted((p.stat().st_size, p.name) for p in (out / "eval").iterdir())
    print(f"{len(report['cases'])} case docs and 1 run doc in {out.relative_to(HERE.parent)} "
          f"(largest {sizes[-1][0] // 1024} KB, {sizes[-1][1]})")


if __name__ == "__main__":
    main()
