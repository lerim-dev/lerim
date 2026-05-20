"""Run the pinned AgentMemory upstream baseline with the standard output path."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path


def main() -> None:
    """Run the AgentMemory pinned baseline benchmark."""
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from benchmarks.competitors.agentmemory_baseline import (
        DEFAULT_AGENTMEMORY_COMMIT,
        DEFAULT_SOURCE_FILES,
        run,
    )

    output_dir = run(
        Namespace(
            agentmemory_commit=DEFAULT_AGENTMEMORY_COMMIT,
            source_files=list(DEFAULT_SOURCE_FILES),
            output_dir=Path("benchmarks/results/raw/agentmemory-pinned-baseline"),
            timeout_seconds=30.0,
        )
    )
    print(f"AgentMemory pinned baseline report written to {output_dir}")


if __name__ == "__main__":
    main()
