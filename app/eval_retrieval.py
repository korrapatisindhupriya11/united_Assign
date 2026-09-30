"""Run the fixed question set and print whether retrieval stayed on the right policy."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.config import ROOT, get_settings
from app.orchestrator import Orchestrator


def main() -> int:
    cases = json.loads((ROOT / "tests" / "golden_questions.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        settings = get_settings().with_overrides(
            llm_backend="extractive",
            feedback_path=tmp_path / "feedback.jsonl",
            audit_path=tmp_path / "audit.jsonl",
        )
        guide = Orchestrator.from_settings(settings)
        failed = 0
        for case in cases:
            result = guide.chat(None, case["question"])
            documents = [source["document_id"] for source in result.sources]
            if case["should_answer"]:
                ok = (not result.refused) and case["expect_doc"] in documents
            else:
                ok = result.refused and not documents
            mark = "ok" if ok else "FAIL"
            if not ok:
                failed += 1
            top = documents[0] if documents else "-"
            print(f"[{mark}] {case['question']}")
            print(f"     refused={result.refused} top={top} confidence={result.confidence}")
        print(f"\n{len(cases) - failed}/{len(cases)} passed")
        return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
