#pragma once

// Software-only radio labels. No SX1262 hardware or RF transmission is used.
#define HIMRAKSHAK_RADIO_FREQUENCY_MHZ 868.0
#define HIMRAKSHAK_RADIO_BANDWIDTH_KHZ 125
#define HIMRAKSHAK_RADIO_SPREADING_FACTOR 9
#define HIMRAKSHAK_RADIO_CODING_RATE "4/5"

#define HIMRAKSHAK_V2_TRANSMISSION_PATH "/api/v2/radio/transmissions"

// Define HIMRAKSHAK_DEVICE_TOKEN outside tracked source only if a future
// least-privilege device-authentication mechanism is deployed. This is not an
// admin key and the current Phase 5 server does not accept this header.
#ifndef HIMRAKSHAK_DEVICE_TOKEN
#define HIMRAKSHAK_DEVICE_TOKEN ""
#endif
