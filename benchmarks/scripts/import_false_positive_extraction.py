"""Import the current negative-case extraction diagnostic as a sanitized artifact."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path


def main() -> None:
    """Import the default false-positive extraction report."""
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from benchmarks.lerim_evidence.false_positive_extraction import (
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
    print(f"False-positive extraction report written to {output_dir}")


if __name__ == "__main__":
    main()
