"""Load per-item Score-stage samples from a Run-stage artifact dir (plan 4.5).

Each item dir under `eval/runs/<run-id>/<id>/` holds `report.md` (the answer),
`evidence.jsonl` (the retrieved contexts), and `result.json` (the carrier of `question`,
`reference`, target, etc.). A "sample" is the bundle Ragas (B2) needs in one place:

    {id, question, answer, contexts, reference, target}

Failed items (`result.json{failed: true}`) are skipped — they have no answer to score.
"""

import json
from pathlib import Path


def load_item_samples(run_dir: Path) -> list[dict]:
    """Return one sample per successful item in `run_dir`. Order is sorted-by-id for
    deterministic output across re-scores."""
    samples: list[dict] = []
    for item_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        result_path = item_dir / "result.json"
        report_path = item_dir / "report.md"
        evidence_path = item_dir / "evidence.jsonl"
        if not result_path.is_file():
            continue
        result = json.loads(result_path.read_text())
        if result.get("failed"):
            continue
        # Missing report/evidence on a non-failed item is a Run-stage bug — surface loudly.
        if not report_path.is_file() or not evidence_path.is_file():
            raise FileNotFoundError(
                f"{item_dir.name}: result.json says not failed but report.md / evidence.jsonl is missing"
            )
        contexts = [
            json.loads(line)["content"]
            for line in evidence_path.read_text().splitlines()
            if line.strip()
        ]
        samples.append(
            {
                "id": result["id"],
                "question": result["question"],
                "answer": report_path.read_text(),
                "contexts": contexts,
                "reference": result["reference"],
                "target": result["target"],
            }
        )
    return samples
