(function (root) {
  "use strict";
  var H = root.HimRakshak = root.HimRakshak || {};
  var pollTimer = null;
  var refreshPromise = null;
  var routeTitles = {
    overview: "Overview",
    stations: "Sensor stations",
    "live-monitoring": "Live monitoring",
    "lora-network": "Virtual LoRa lab",
    "simulation-lab": "Simulation lab",
    "alerts-events": "Alerts & events",
    diagnostics: "Diagnostics"
  };
  var localHostnames = ["localhost", "127.0.0.1", "::1"];

  function pageMode() {
    if (H.api.isStandalone()) return "standalone";
    return localHostnames.indexOf(root.location.hostname) >= 0 ? "local" : "cloud";
  }

  function errorText(error) {
    if (!error) return "The backend is unavailable.";
    if (error.status === 401) return "Administrative authorization is required for this operation.";
    if (error.status === 403) return "This protected operation is disabled in cloud mode.";
    if (error.status === 404) return "The requested station or endpoint was not found.";
    if (error.status === 409) {
      if (error.classification === "duplicate") return "The packet was already accepted; backend state was not replaced.";
      if (error.classification === "stale") return "The packet sequence is stale; backend state was not replaced.";
      return error.message;
    }
    if (error.status === 429) return error.message + (error.retryAfter ? " Retry after " + error.retryAfter + " seconds." : "");
    if (error.kind === "timeout") return error.message + " Last known state is preserved.";
    return error.message || "The backend is unavailable. Last known state is preserved.";
  }

  function setMode(mode) {
    H.state.set({mode: mode});
    var badge = H.q("#mode");
    if (badge) {
      badge.textContent = H.mappers.modeLabel(mode);
      badge.className = "badge " + (mode === "local" || mode === "cloud" ? "ok" : "offline");
    }
  }

  function stationList(state) {
    return H.mappers.stations(state.overview);
  }

  function currentStation(state) {
    var list = stationList(state);
    return list.filter(function (station) { return station.node_id === state.station; })[0] || null;
  }

  function latestFor(station) {
    return station && station.latest ? station.latest : null;
  }

  function readingCell(reading, field, suffix) {
    var value = reading && reading[field];
    return value === undefined || value === null ? "—" : H.escape(value) + (suffix || "");
  }

  function assessmentBadge(assessment) {
    var level = assessment && assessment.risk_level;
    return '<span class="badge ' + H.mappers.risk(level) + '">' + H.escape(level || "UNAVAILABLE") + "</span>";
  }

  function statusBadge(value) {
    var text = String(value || "unavailable").replace(/_/g, " ").toUpperCase();
    var cls = value === "available" || value === "accepted" || value === "live" || value === "monitoring" || value === "connected" ? "ok" :
      value === "warning" || value === "delayed" || value === "recovering" || value === "retrying" ? "warning" : "offline";
    return '<span class="badge ' + cls + '">' + H.escape(text) + "</span>";
  }

  function unwrapV2(payload) {
    return payload && payload.data ? payload.data : payload;
  }

  function stateNotice(state) {
    if (state.loading && !state.overview) return '<div class="empty">Loading backend state…</div>';
    if (state.error) {
      return '<div class="alert"><strong>' + H.escape(H.mappers.modeLabel(state.mode)) + '</strong><br>' +
        H.escape(errorText(state.error)) + (state.stale ? "<br>Showing last known backend state." : "") + "</div>";
    }
    if (state.stale) return '<div class="alert"><strong>STALE BACKEND STATE</strong><br>Polling is unavailable; displayed telemetry is not being refreshed.</div>';
    return "";
  }

  function renderTable(state, title, filter) {
    var stations = stationList(state).filter(filter || function () { return true; });
    var html = '<div class="card"><h2>' + H.escape(title) + '</h2><p class="muted">Backend risk authority · accepted v1 telemetry only.</p><div class="table-wrap"><table class="table"><thead><tr><th>Station</th><th>Risk</th><th>Moisture</th><th>Tilt</th><th>Vibration</th><th>Battery</th><th>Sequence</th></tr></thead><tbody>';
    if (!stations.length) html += '<tr><td colspan="7" class="empty">No backend station data is available.</td></tr>';
    stations.forEach(function (station) {
      var latest = latestFor(station);
      var reading = H.mappers.reading(latest);
      var assessment = H.mappers.assessment(latest);
      html += '<tr><td><button class="btn secondary" data-select="' + H.escape(station.node_id) + '">' + H.escape(station.node_id) + '</button><small class="muted">' + H.escape(station.label || "") + "</small></td>" +
        "<td>" + assessmentBadge(assessment) + "</td>" +
        '<td class="mono">' + readingCell(reading, "soil_moisture_pct", "%") + "</td>" +
        '<td class="mono">' + readingCell(reading, "tilt_deg", "°") + "</td>" +
        '<td class="mono">' + readingCell(reading, "vibration_level") + "</td>" +
        '<td class="mono">' + readingCell(reading, "battery_pct", "%") + "</td>" +
        '<td class="mono">' + H.escape(station.next_sequence === undefined ? "—" : station.next_sequence) + "</td></tr>";
    });
    return html + "</tbody></table></div></div>";
  }

  function renderDetail(state) {
    var station = H.mappers.station({station: state.detail}) || currentStation(state);
    if (!station) return '<div class="card"><div class="empty">Select a station to inspect its backend state.</div></div>';
    var latest = latestFor(station);
    var reading = H.mappers.reading(latest);
    var assessment = H.mappers.assessment(latest);
    var events = H.mappers.eventList(station, []);
    var communication = station.communication || {};
    var html = '<div class="card"><h2>' + H.escape(station.node_id) + ' · ' + H.escape(station.label || "Virtual station") + "</h2>" +
      '<p class="muted">Scenario: ' + H.escape(station.scenario || "normal") + " · receiver: " + H.escape(station.receiver_connected === false ? "disconnected" : "connected") + "</p>";
    if (!latest) return html + '<div class="empty">No accepted reading for this station.</div></div>';
    html += '<div class="grid grid-4"><div><div class="muted">Risk</div>' + assessmentBadge(assessment) + '</div><div><div class="muted">Demo score</div><div class="kpi-value mono">' + H.escape(assessment.demo_score === undefined ? "—" : assessment.demo_score) + "</div></div>" +
      '<div><div class="muted">Device sequence</div><div class="kpi-value mono">' + H.escape(reading.sequence) + "</div></div><div><div class=\"muted\">Sensor timestamp</div><div class=\"mono\">" + H.escape(H.formatTime(reading.timestamp)) + "</div></div></div>" +
      '<div class="grid grid-4 telemetry"><div><div class="muted">Moisture</div><div class="kpi-value mono">' + readingCell(reading, "soil_moisture_pct", "%") + "</div></div><div><div class=\"muted\">Tilt</div><div class=\"kpi-value mono\">" + readingCell(reading, "tilt_deg", "°") + "</div></div><div><div class=\"muted\">Vibration</div><div class=\"kpi-value mono\">" + readingCell(reading, "vibration_level") + "</div></div><div><div class=\"muted\">Battery</div><div class=\"kpi-value mono\">" + readingCell(reading, "battery_pct", "%") + "</div></div></div>" +
      '<p class="notice">' + H.escape((assessment.reasons || []).join(" · ") || "No backend risk reasons supplied.") + "</p>" +
      '<p class="muted">Device: ' + statusBadge(communication.device_state) + " · radio: " + statusBadge(communication.radio_state) + " · ingestion: " + statusBadge(communication.ingestion_state) + " · pending " + H.escape(communication.pending_packets === undefined ? "—" : communication.pending_packets) + " · delivered " + H.escape(communication.packets_delivered === undefined ? "—" : communication.packets_delivered) + " · dropped " + H.escape(communication.packets_dropped === undefined ? "—" : communication.packets_dropped) + "</p>" +
      '<h3>Accepted event history</h3>' + renderEvents(events) + "</div>";
    return html;
  }

  function renderEvents(events) {
    if (!events.length) return '<div class="empty">No accepted events available.</div>';
    return '<div class="timeline">' + events.map(function (event) {
      var reading = event.reading || {};
      var assessment = event.assessment || {};
      return '<div class="event"><span class="event-dot"></span><div><strong>' + H.escape(reading.node_id || "") + " · sequence " + H.escape(reading.sequence) + '</strong><small>Sensor: ' + H.escape(H.formatTime(reading.timestamp)) + " · reasons: " + H.escape((assessment.reasons || []).join(" · ") || "none") + "</small></div>" + assessmentBadge(assessment) + "</div>";
    }).join("") + "</div>";
  }

  function renderOverview(state) {
    return stateNotice(state) + renderTable(state, "Overview dashboard") + renderDetail(state);
  }

  function renderStations(state) {
    var options = stationList(state).map(function (station) {
      return '<option value="' + H.escape(station.node_id) + '"' + (station.node_id === state.station ? " selected" : "") + ">" + H.escape(station.node_id) + "</option>";
    }).join("");
    return stateNotice(state) + '<div class="toolbar"><label for="station-picker">Selected station</label><select id="station-picker">' + options + "</select></div>" + renderTable(state, "Sensor stations") + renderDetail(state);
  }

  function renderLive(state) {
    var station = H.mappers.station({station: state.detail});
    var events = H.mappers.eventList(station, state.events);
    return stateNotice(state) + '<div class="card"><h2>Live monitoring</h2><p class="muted">Accepted backend events. Sensor timestamps are distinct from browser render time.</p>' + renderEvents(events) + "</div>";
  }

  function renderAlerts(state) {
    var station = H.mappers.station({station: state.detail});
    var events = H.mappers.eventList(station, state.events).filter(function (event) {
      return event.assessment && event.assessment.risk_level !== "NORMAL";
    });
    return stateNotice(state) + '<div class="toolbar"><button class="btn" id="export-events">Export CSV</button><span class="muted">Backend accepted events only; browser-local simulations remain separate.</span></div><div class="card"><h2>Alerts &amp; events</h2>' + renderEvents(events) + "</div>";
  }

  function renderSimulation(state) {
    var protectedMode = state.mode === "cloud" || state.mode === "cloud-unavailable";
    var result = state.error ? errorText(state.error) : "Choose a supported scenario.";
    return stateNotice(state) + '<div class="card"><h2>Simulation Lab</h2><p class="muted">SOFTWARE SIMULATION · supported v1 scenarios only</p><div class="toolbar"><label for="sim-station">Station <select id="sim-station">' +
      stationList(state).map(function (station) { return '<option value="' + H.escape(station.node_id) + '"' + (station.node_id === state.station ? " selected" : "") + ">" + H.escape(station.node_id) + "</option>"; }).join("") +
      '</select></label><button class="btn" data-scenario="normal">Reset</button><button class="btn" data-scenario="heavy_rain">Heavy rain</button><button class="btn" data-scenario="slope_shift">Slope shift</button><button class="btn" data-scenario="vibration_burst">Vibration burst</button></div><div id="sim-result" class="empty">' +
      H.escape(protectedMode ? "Protected simulation requires local backend mode." : result) + "</div><p class=\"muted\">Cloud mode is read-only. No admin credential is sent by browser code.</p></div>";
  }

  function renderDiagnostics(state) {
    var gateway = state.gateway || {};
    var radio = state.radio || {};
    var stationRadio = state.stationRadio || {};
    return stateNotice(state) + '<div class="grid grid-3"><div class="card"><div class="muted">Backend mode</div><div class="kpi-value">' + H.escape(H.mappers.modeLabel(state.mode)) + "</div></div><div class=\"card\"><div class=\"muted\">Data state</div><div class=\"kpi-value\">" + statusBadge(state.dataState) + "</div><small class=\"muted\">Browser refresh: " + H.escape(H.formatTime(state.lastRefreshAt)) + "</small></div><div class=\"card\"><div class=\"muted\">Risk authority</div><div class=\"kpi-value\">BACKEND</div><small class=\"muted\">Radio: " + H.escape(radio.profile || "unavailable") + "</small></div></div>" +
      '<div class="grid grid-4"><div class="card"><div class="muted">Gateway</div><div class="kpi-value">' + statusBadge(gateway.gateway_state || (gateway.available ? "available" : "unavailable")) + '</div><small class="muted">Last reception: ' + H.escape(H.formatTime(gateway.last_received_packet_at)) + "</small></div><div class=\"card\"><div class=\"muted\">Channel</div><div class=\"kpi-value\">" + statusBadge(gateway.channel_state) + "</div><small class=\"muted\">Queued: " + H.escape(gateway.queued_packets === undefined ? "—" : gateway.queued_packets) + "</small></div><div class=\"card\"><div class=\"muted\">Ingestion</div><div class=\"kpi-value\">" + statusBadge(gateway.ingestion_state) + "</div><small class=\"muted\">Forwarded: " + H.escape(gateway.last_successful_forward_at ? H.formatTime(gateway.last_successful_forward_at) : "Unavailable") + "</small></div><div class=\"card\"><div class=\"muted\">Selected station radio</div><div class=\"kpi-value\">" + statusBadge(stationRadio.radio_state || stationRadio.connection_state) + "</div><small class=\"muted\">Pending: " + H.escape(stationRadio.pending_transmissions === undefined ? "—" : stationRadio.pending_transmissions) + "</small></div></div>" +
      '<div class="card"><h2>Recovery diagnostics</h2><p class="muted">Software simulation only. No physical RF metrics or crash persistence are claimed.</p><div class="timeline">' + (state.recoveryEvents || []).map(function (event) { return '<div class="event"><span class="event-dot"></span><div><strong>' + H.escape(event.state || "state change") + '</strong><small>' + H.escape(H.formatTime(event.at)) + " · " + H.escape(event.message || "") + "</small></div></div>"; }).join("") + "</div></div>";
  }

  function renderLora(state) {
    var gateway = state.gateway || {};
    return stateNotice(state) + '<div class="card"><h2>Virtual LoRa Network Laboratory</h2><p class="muted">Software reliability outcomes, not physical RF measurements.</p><div class="grid grid-4"><div><div class="muted">Channel</div>' + statusBadge(gateway.channel_state) + '</div><div><div class="muted">Gateway</div>' + statusBadge(gateway.gateway_state || "unavailable") + '</div><div><div class="muted">Ingestion</div>' + statusBadge(gateway.ingestion_state) + '</div><div><div class="muted">Data freshness</div>' + statusBadge(state.freshness) + '</div></div><p class="muted">Queued transmissions: ' + H.escape(gateway.queued_packets === undefined ? "—" : gateway.queued_packets) + ' · delivered: ' + H.escape(gateway.delivered_transmissions === undefined ? "—" : gateway.delivered_transmissions) + ' · dropped: ' + H.escape(gateway.dropped_transmissions === undefined ? "—" : gateway.dropped_transmissions) + '</p></div>' + renderTable(state, "Station communication state");
  }

  function renderRoute(route) {
    var state = H.state.get();
    H.qAll(".route").forEach(function (section) {
      section.classList.toggle("active", section.id === "route-" + route);
    });
    H.qAll(".nav button").forEach(function (button) {
      button.setAttribute("aria-current", button.getAttribute("data-route") === route ? "true" : "false");
    });
    var title = H.q("#page-title");
    if (title) title.textContent = routeTitles[route] || "HimRakshak";
    var rootSection = H.q("#route-" + route);
    if (!rootSection) return;
    var renderer = {
      overview: renderOverview,
      stations: renderStations,
      "live-monitoring": renderLive,
      "lora-network": renderLora,
      "simulation-lab": renderSimulation,
      "alerts-events": renderAlerts,
      diagnostics: renderDiagnostics
    }[route] || renderOverview;
    rootSection.innerHTML = renderer(state);
    bindRoute(route);
  }

  function bindRoute(route) {
    var stationPicker = H.q("#station-picker");
    if (stationPicker) stationPicker.addEventListener("change", function () {
      H.state.selectStation(stationPicker.value);
      refresh(true);
    });
    H.qAll("[data-select]").forEach(function (button) {
      button.addEventListener("click", function () {
        H.state.selectStation(button.getAttribute("data-select"));
        H.router.go("stations");
        refresh(true);
      });
    });
    var simStation = H.q("#sim-station");
    if (simStation) simStation.addEventListener("change", function () { H.state.selectStation(simStation.value); });
    H.qAll("[data-scenario]").forEach(function (button) {
      button.addEventListener("click", function () { runScenario(button.getAttribute("data-scenario")); });
    });
    var exportButton = H.q("#export-events");
    if (exportButton) exportButton.addEventListener("click", exportEvents);
  }

  function runScenario(scenario) {
    var state = H.state.get();
    var station = H.q("#sim-station");
    var stationId = station ? station.value : state.station;
    var result = H.q("#sim-result");
    if (state.mode === "standalone") {
      var presets = {
        normal: [32, 0.9, 11],
        heavy_rain: [78, 1.4, 22],
        slope_shift: [48, 4.8, 28],
        vibration_burst: [35, 1.1, 82]
      };
      var preset = presets[scenario] || presets.normal;
      var event = {reading: {node_id: stationId, sequence: state.browserEvents.length, timestamp: "SIMULATED", soil_moisture_pct: preset[0], tilt_deg: preset[1], vibration_level: preset[2], battery_pct: 82}, assessment: {risk_level: scenario === "slope_shift" ? "WARNING" : "NORMAL", demo_score: 0, reasons: ["Browser-local simulation"], illustrative: true}};
      H.state.set({browserEvents: [event].concat(state.browserEvents).slice(0, 50)});
      if (result) result.textContent = "Browser-local simulation recorded; backend history was not changed.";
      return;
    }
    if (state.mode !== "local") {
      if (result) result.textContent = "Protected simulation requires local backend mode.";
      return;
    }
    if (result) result.textContent = "Submitting scenario to the backend…";
    H.api.simulate(stationId, scenario).then(function () {
      if (result) result.textContent = "Backend accepted scenario " + scenario + " and recalculated risk.";
      refresh(true);
    }).catch(function (error) {
      if (result) result.textContent = errorText(error);
      H.state.set({error: error});
    });
  }

  function exportEvents() {
    var state = H.state.get();
    var station = H.mappers.station({station: state.detail});
    var events = H.mappers.eventList(station, state.events).concat(state.browserEvents || []);
    var rows = [["timestamp", "event_source", "node_id", "sequence", "soil_moisture_pct", "tilt_deg", "vibration_level", "battery_pct", "risk", "reasons"]];
    events.forEach(function (event) {
      var reading = event.reading || {};
      var assessment = event.assessment || {};
      rows.push([reading.timestamp, event === (state.browserEvents || [])[0] ? "browser-local" : "backend-accepted", reading.node_id, reading.sequence, reading.soil_moisture_pct, reading.tilt_deg, reading.vibration_level, reading.battery_pct, assessment.risk_level, (assessment.reasons || []).join(" | ")]);
    });
    H.controls.csv(rows);
  }

  function refresh(force) {
    var state = H.state.get();
    if (H.api.isStandalone()) {
      setMode("standalone");
      H.state.set({loading: false, error: null, stale: false});
      return Promise.resolve();
    }
    if (state.refreshInFlight) {
      if (!force) return refreshPromise;
      return refreshPromise.then(function () { return refresh(false); }, function () { return refresh(false); });
    }
    var stationId = state.station;
    var generation = state.generation + 1;
    H.state.set({refreshInFlight: true, loading: !state.overview});
    function optional(request) {
      return request().catch(function (error) { return { unavailable: true, error: error }; });
    }
    refreshPromise = Promise.all([H.api.health(), H.api.state(), H.api.stations(), H.api.station(stationId), optional(H.api.radioStatus), optional(H.api.gatewayHealth), optional(function () { return H.api.radioDiagnostics(stationId); })]).then(function (responses) {
      var latest = H.state.get();
      if (latest.generation !== generation - 1 || latest.station !== stationId) return;
      setMode(pageMode());
      var gateway = unwrapV2(responses[5]);
      var previousState = latest.dataState;
      var stationDetail = H.mappers.station(responses[3]);
      var freshness = H.mappers.freshness(H.mappers.reading(latestFor(stationDetail)).timestamp);
      var dataState = freshness;
      var recoveryEvents = latest.recoveryEvents || [];
      if (previousState !== "live" && dataState === "live") {
        recoveryEvents = [{state: "recovered", at: new Date().toISOString(), message: "Backend telemetry refresh recovered."}].concat(recoveryEvents).slice(0, 20);
      }
      H.state.set({
        health: responses[0],
        events: responses[1] && Array.isArray(responses[1].events) ? responses[1].events : [],
        overview: responses[2],
        detail: stationDetail,
        radio: unwrapV2(responses[4]),
        gateway: gateway,
        stationRadio: unwrapV2(responses[6]),
        dataState: dataState,
        freshness: freshness,
        recoveryEvents: recoveryEvents,
        loading: false,
        stale: false,
        error: null,
        lastSuccessAt: new Date().toISOString(),
        lastRefreshAt: new Date().toISOString()
      });
    }).catch(function (error) {
      var latest = H.state.get();
      if (latest.generation !== generation - 1 || latest.station !== stationId) return;
      setMode(pageMode() === "local" ? "local-unavailable" : "cloud-unavailable");
      H.state.set({loading: false, stale: Boolean(latest.overview), dataState: latest.overview ? "disconnected" : "unavailable", error: error, lastRefreshAt: new Date().toISOString()});
    }).finally(function () {
      H.state.set({refreshInFlight: false});
    });
    return refreshPromise;
  }

  function startPolling() {
    if (H.api.isStandalone()) return;
    if (pollTimer) root.clearInterval(pollTimer);
    pollTimer = root.setInterval(function () {
      if (!document.hidden) refresh(false);
    }, 5000);
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) refresh(true);
    });
  }

  H.app = {
    start: function () {
      H.shell.init();
      H.router.init(renderRoute);
      H.state.subscribe(function () {
        var route = H.router.current();
        renderRoute(route);
        var badge = H.q("#mode");
        if (badge) badge.textContent = H.mappers.modeLabel(H.state.get().mode);
      });
      setMode(H.state.get().mode);
      refresh(false);
      startPolling();
    },
    refresh: refresh
  };
  root.addEventListener("DOMContentLoaded", H.app.start);
})(window);
