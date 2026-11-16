# Virtual LoRa channel simulator

HimRakshak's Phase 4 simulator is a software-only transport model for HR-01,
HR-02, and HR-03. It is intentionally independent from the HTTP API,
`StationManager`, frontend, risk engine, and Wokwi firmware. It produces
explicitly simulated airtime, link metrics, delivery outcomes, and statistics;
it never transmits an RF signal.

## Default profile

`RadioProfile()` uses the proposed experiment profile:

| Setting | Value |
| --- | --- |
| Frequency | 868.0 MHz |
| Bandwidth | 125 kHz |
| Spreading factor | SF9 |
| Coding rate | 4/5 |
| Transmit power | 14 dBm |
| Preamble | 8 symbols |
| Header | Explicit |
| CRC | Enabled |

868 MHz is a simulation parameter, not a statement of regulatory permission.
SF7 through SF12 and the validated LoRa bandwidth set are supported. The PHY
payload limit defaults to 255 bytes and oversized payloads are rejected.

## Airtime

The implementation uses the LoRa PHY equations rather than a fixed delay:

* `Tsym = 2^SF / BW`
* `Tpreamble = (Npreamble + 4.25) * Tsym`
* payload symbols use the documented CRC, header, coding-rate, and
  low-data-rate optimization terms.

For the default SF9/125 kHz/4/5 profile and a 10-byte payload, `Tsym` is
4.096 ms, payload symbols are 23, and total airtime is 144.384 ms.
Low-data-rate optimization is enabled automatically when symbol duration is at
least 16 ms, with a validated explicit override for experiments.

## Link model

`ChannelConditions` provides distance, terrain, path-loss exponent, reference
distance, obstruction loss, and optional deterministic shadowing. Free-space
loss is `20 log10(4*pi*d/lambda)`. A reference-distance path-loss model is
combined with that lower bound, then terrain and shadowing are applied.

RSSI is transmit power plus antenna gains minus path loss. Noise floor is
`-174 + 10 log10(BW) + noise figure` dBm. SNR, approximate SF-specific
sensitivity, and link margin are derived from those values. The default
clear/moderate/heavy obstruction values are software assumptions, not
Himalayan measurements. Delivery probability is a bounded simulation heuristic
based on link margin and configured packet-loss probability.

These metrics do not establish radio range, field reliability, or actual
SX1262 performance.

## Packet lifecycle and virtual time

```python
from himrakshak.lora_simulator import (
    ChannelConditions, LoRaPacket, VirtualLoRaChannel
)

channel = VirtualLoRaChannel(seed=42, queue_capacity=256)
packet = LoRaPacket("reading-1", "attempt-1", "HR-01", 0, 1, b"telemetry")
result = channel.transmit(packet, ChannelConditions(base_delay_ms=25))

channel.advance_time(result.metrics.airtime_ms + 25)
received = channel.receive_ready()
```

`transmit()` validates the packet, calculates metrics, evaluates gateway
availability and delivery probability, then schedules primary and optional
duplicate copies. It returns `queued`, `lost`, `gateway_unavailable`, or
`queue_full` with a machine-readable reason. A queued packet is not yet
received. `advance_time()` never sleeps; `receive_ready()` returns only events
whose simulated receive time has arrived.

The queue is a bounded priority queue ordered by scheduled receive time.
Duplicate copies preserve the logical packet and attempt IDs and expose a copy
index. Reordering adds configurable delay. If a duplicate cannot fit, the
primary remains queued and the result records duplicate rejection. Bounded
history prevents unbounded diagnostic memory growth.

## Determinism and statistics

Random decisions use a stable SHA-256-derived seed from the global seed,
packet identity, attempt identity, attempt number, and decision type. Thus the
same inputs reproduce the same metrics and outcome without relying on Python's
process-randomized `hash()` or on unrelated packet order.

`get_statistics()` and `get_node_statistics()` report transmission attempts,
losses, gateway failures, queue rejections, primary deliveries, duplicate
copies, pending depth, simulated airtime, average simulated RSSI/SNR, and an
explicit `simulated_channel_delivery_ratio`. Diagnostic history is bounded and
marked `software_simulation`.

## Phase 8 reliability boundary

The simulator distinguishes loss, queue-full, gateway-unavailable, duplicate
copies, and successful delivery. It does not retry packets itself: retry
identity and backoff belong to the sender, while sequence reconciliation and
backend acceptance belong to the gateway and station manager. A gateway outage
does not remove already scheduled packets; the gateway controls whether due
packets are consumed, allowing deterministic recovery after virtual time
advances.

## Phase 5 boundary

The future gateway can submit a `LoRaPacket`, inspect the immediate
`TransmissionResult`, advance simulated time, and consume `ReceivedPacket`
objects. The gateway—not this module—will call the existing station manager,
perform sequence reconciliation, and apply risk authority. No Phase 5 gateway,
HTTP route, v2 endpoint, frontend radio screen, LoRaWAN implementation, solar
model, battery model, or hardware integration is included here.

## Limitations

This is a simplified software channel. It has no SX1262 hardware, no actual RF
signals, no regulatory-compliance claim, no LoRaWAN protocol, and no field
calibration. RSSI, SNR, airtime, loss, and range-like behaviour are simulated
assumptions and must not be presented as measured Himalayan performance.
