#pragma once

#include <Arduino.h>
#include "radio_config.h"

inline String makeAttemptId(const String &packetId, unsigned long attemptNumber) {
  return packetId + "-a" + String(attemptNumber);
}

inline String makeTransmissionEnvelope(
    const String &transmissionId,
    const String &idempotencyKey,
    const String &nodeId,
    unsigned long sequence,
    const String &payload,
    unsigned long attemptNumber) {
  String envelope = "{\"transmission_id\":\"";
  envelope += transmissionId;
  envelope += "\",\"idempotency_key\":\"";
  envelope += idempotencyKey;
  envelope += "\",\"node_id\":\"";
  envelope += nodeId;
  envelope += "\",\"device_sequence\":";
  envelope += sequence;
  envelope += ",\"created_at\":\"SIMULATED\",\"payload\":";
  envelope += payload;
  envelope += ",\"channel_profile\":\"baseline\",\"attempt_number\":";
  envelope += attemptNumber;
  envelope += "}";
  return envelope;
}
