"""
Max-flow scheduler for auto-run mode.

Generates all model-combination permutations from auto_run_config.yaml,
displays cost/time estimate and requires user confirmation, then distributes
combinations across N parallel workers. Scans runs.jsonl on startup to
skip already-completed combinations (checkpoint + resume).
"""

# TODO: implement
