(function (root) {
  "use strict";
  var H = root.HimRakshak = root.HimRakshak || {};
  function first(value, fallback) { return value === undefined || value === null ? fallback : value; }
  H.mappers = {
    modeLabel: function (mode) {
      return {
        standalone: "STANDALONE SIMULATION",
        local: "LOCAL BACKEND CONNECTED",
        cloud: "CLOUD BACKEND CONNECTED",
        "local-unavailable": "LOCAL BACKEND UNAVAILABLE",
        "cloud-unavailable": "CLOUD BACKEND UNAVAILABLE",
        connecting: "CONNECTING"
      }[mode] || "BACKEND UNAVAILABLE";
    },
    risk: function (value) {
      var level = String(value || "").toUpperCase();
      return level === "CRITICAL" ? "critical" : level === "WARNING" ? "warning" : level === "NORMAL" ? "ok" : "offline";
    },
    stations: function (payload) {
      return payload && Array.isArray(payload.stations) ? payload.stations : [];
    },
    station: function (payload) {
      return payload && payload.station ? payload.station : null;
    },
    reading: function (payload) {
      if (!payload) return {};
      return payload.reading || (payload.latest && payload.latest.reading) || {};
    },
    assessment: function (payload) {
      if (!payload) return {};
      return payload.assessment || (payload.latest && payload.latest.assessment) || {};
    },
    eventList: function (station, globalEvents) {
      var events = station && Array.isArray(station.events) ? station.events : globalEvents || [];
      return events.slice().sort(function (left, right) {
        return String((right.reading || {}).timestamp || "").localeCompare(String((left.reading || {}).timestamp || ""));
      });
    },
    ageSeconds: function (timestamp, now) {
      if (!timestamp || timestamp === "SIMULATED") return null;
      var value = new Date(timestamp).getTime();
      if (!isFinite(value)) return null;
      return Math.max(0, Math.floor(((now || Date.now()) - value) / 1000));
    },
    value: first
  };
})(window);
