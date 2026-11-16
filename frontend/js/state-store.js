(function (root) {
  "use strict";
  var H = root.HimRakshak = root.HimRakshak || {};
  var listeners = [];
  var state = {
    mode: root.location.protocol === "file:" ? "standalone" : "connecting",
    health: null,
    overview: null,
    detail: null,
    radio: null,
    stationRadio: null,
    gateway: null,
    dataState: "unavailable",
    freshness: null,
    recoveryEvents: [],
    station: "HR-01",
    events: [],
    browserEvents: [],
    loading: true,
    stale: false,
    error: null,
    lastSuccessAt: null,
    refreshInFlight: false,
    lastRefreshAt: null,
    generation: 0
  };

  H.state = {
    get: function () { return state; },
    set: function (patch) {
      Object.keys(patch || {}).forEach(function (key) { state[key] = patch[key]; });
      listeners.slice().forEach(function (listener) { listener(state); });
    },
    subscribe: function (listener) {
      listeners.push(listener);
      return function () {
        var index = listeners.indexOf(listener);
        if (index >= 0) listeners.splice(index, 1);
      };
    },
    selectStation: function (id) {
      if (id && id !== state.station) {
        state.station = id;
        state.detail = null;
        state.generation += 1;
        listeners.slice().forEach(function (listener) { listener(state); });
      }
      return state.station;
    }
  };
})(window);
