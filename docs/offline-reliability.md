# Offline reliability and recovery

Phase 8 makes loss of connectivity an explicit state instead of treating it
as a successful telemetry update. The implementation remains software-only and
keeps API v1, backend risk authority, and the existing Phase 5 transmission
boundary unchanged.

## State machines

### Device

```text
initializing -> monitoring
monitoring -> offline_queueing       (Wi-Fi/backend unavailable)
offline_queueing -> retrying         (retry window opens)
retrying -> monitoring               (accepted delivery)
retrying -> offline_queueing         (temporary failure)
retrying -> local_only               (permanent authorization/schema failure)
offline_queueing -> queue_full        (bounded FIFO exhausted)
any state -> sensor_fault             (invalid local acquisition)
```

Local sensor sampling and alert indicators continue in every state except
`sensor_fault`. The queue is a ten-entry RAM FIFO. Overflow is explicit and
does not invent an accepted reading; a restart discards queued packets.

### Gateway and ingestion

The virtual gateway reports `available`, `recovering`, or `unavailable`.
Channel state separately reports queued, delivered, lost, or unavailable.
Ingestion reports pending, accepted, duplicate, stale, schema-rejected, or
backend-unavailable. When the gateway is down, due channel packets remain
queued rather than being drained and discarded. Recovery consumes them using
the normal schema, sequence, and backend risk pipeline.

## Retry policy

Network errors, timeouts, HTTP 429, and HTTP 5xx are temporary. Retries use
capped exponential backoff; `Retry-After` is honored for 429 responses and is
also bounded. HTTP 400, 401, 403, 404, and 409 are permanent for the current
packet and are removed from the retry queue. The firmware never embeds an
admin credential, and no retry policy bypasses server authorization.

Logical packet identity remains stable across attempts. Each attempt receives
a new transmission identity, so a retry can be observed without allowing a
duplicate accepted station event. Equal backend sequences are duplicates;
lower sequences are stale; only higher sequences are accepted.

## Frontend behavior

The frontend displays live, delayed, stale, disconnected, and unavailable
states based on backend timestamps and request outcomes. It polls read-only
radio, gateway, and station diagnostics as additive data. A diagnostics
failure cannot replace a valid station reading, and cloud mode remains
read-only. Recovery adds a browser-local timeline entry only; it never
fabricates sensor telemetry or risk assessments.

## Bounds and limitations

Gateway queues, idempotency caches, station pending packets, and event
histories are bounded in memory. Restart clears these caches and does not
provide durable delivery guarantees. Radio metrics are simulation outputs, not
measurements. The v2 transmission endpoint retains the existing protected
admin boundary; a least-privilege device credential is still required for
future remote firmware submission.

Validation includes deterministic outage/recovery, queue overflow, duplicate
and stale reconciliation, retry identity, firmware source contracts, frontend
state contracts, Python compilation, JavaScript syntax, and the complete
unittest suite.
