
"""
kvlogger.py — structured logging for the KV store, matching the LogLens
log schema locked in Stage 1/2.
 
Design notes (see Obsidian Stage 1/2 doc for full reasoning):
- Writes newline-delimited JSON to a flat file, decoupled from the WAL.
  This file is what LogLens tails. It is NOT the WAL — WAL is for
  crash recovery of data, this file is for observability.
- term is always null (static leadership, no election protocol).
- event_type "election" is in the schema for forward-compatibility but
  is never emitted here, since this KV store has no election mechanism.
- DELETE is logged as event_type "write" (not its own type) to avoid
  expanding the locked schema enum for a minor variant — the distinction
  is captured in a "command" detail field instead.
"""
 
import json
import time
from datetime import datetime, timezone
 
LOG_FILE = "structured.log"
 
 
def _now_iso():
    # ISO 8601 UTC, millisecond precision — required by schema
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
 
 
def log_event(
    event_type,
    node_id,
    role,
    key=None,
    value_size_bytes=None,
    latency_ms=None,
    status="ok",
    replica_targets=None,
    replication_offset=None,
    error_message=None,
    command=None,
):
    entry = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "node_id": node_id,
        "role": role,
        "term": None,  # static leadership — no election, always null
        "key": key,
        "value_size_bytes": value_size_bytes,
        "latency_ms": latency_ms,
        "status": status,
        "replica_targets": replica_targets if replica_targets is not None else [],
        "replication_offset": replication_offset,
        "error_message": error_message,
    }
    if command is not None:
        entry["command"] = command  # extra field, not in core schema — safe to ignore downstream
 
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
 
 
class Timer:
    """Small helper to measure latency_ms around a block of code."""
 
    def __enter__(self):
        self._start = time.perf_counter()
        return self
 
    def __exit__(self, *exc):
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000
 








