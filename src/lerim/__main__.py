"""Allow running Lerim as ``python -m lerim``."""

from lerim.server.cli import main

raise SystemExit(main())
