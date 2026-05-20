"""Import the current full 47-case extraction benchmark as a sanitized artifact."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path


def main() -> None:
    """Import the default full extraction report."""
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from benchmarks.lerim_evidence.extraction_quality import (
        DEFAULT_OUTPUT_DIR,
        DEFAULT_SOURCE_REPORT,
        run,
    )

    output_dir = run(
        Namespace(
            source_report=DEFAULT_SOURCE_REPORT,
            output_dir=DEFAULT_OUTPUT_DIR,
        )
    )
    print(f"Extraction quality report written to {output_dir}")


if __name__ == "__main__":
    main()
