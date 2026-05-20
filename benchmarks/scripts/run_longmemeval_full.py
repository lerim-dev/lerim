"""Run Lerim's full LongMemEval-S hybrid retrieval benchmark."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from benchmarks.lerim_evidence.longmemeval import main


if __name__ == "__main__":
    if len(sys.argv) == 1:
        sys.argv.extend(
            [
                "--retrieval-mode",
                "hybrid",
                "--local-files-only",
                "--progress-every",
                "25",
                "--output-dir",
                "benchmarks/results/raw/longmemeval-hybrid-full",
            ]
        )
    main()
