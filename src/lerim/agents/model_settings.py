"""Shared model settings for Lerim's agent workflows."""

from __future__ import annotations

from pydantic_ai.settings import ModelSettings


# These agents do retrieval, classification, and store maintenance. We keep the
# default sampling low-variance because release testing showed MiniMax M2.7 could
# otherwise drift into valid-looking but unstable wording or tool sequencing.
# If a provider behaves poorly at zero temperature, change this one constant and
# rerun the agent integration suite instead of tuning each agent independently.
LOW_VARIANCE_AGENT_MODEL_SETTINGS = ModelSettings(temperature=0.0, top_p=0.9)
