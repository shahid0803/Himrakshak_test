(function (root) {
  "use strict";
  var H = root.HimRakshak = root.HimRakshak || {};

  function makeError(kind, message, extra) {
    var error = { kind: kind, status: 0, message: message };
    Object.keys(extra || {}).forEach(function (key) { error[key] = extra[key]; });
    return error;
  }

  function parseBody(response) {
    return response.text().then(function (text) {
      if (!text) return null;
      try { return JSON.parse(text); } catch (ignore) {
        return { error: { status: response.status, message: "Backend returned invalid JSON." } };
      }
    });
  }

  function request(path, options) {
    options = options || {};
    if (root.location.protocol === "file:") {
      return Promise.reject(makeError("standalone", "Standalone browser mode has no backend connection."));
    }

    var controller = root.AbortController ? new root.AbortController() : null;
    var timeoutMs = options.timeout || 5000;
    var timer = root.setTimeout(function () {
      if (controller) controller.abort();
    }, timeoutMs);
    var headers = { "Accept": "application/json" };
    if (options.body !== undefined) headers["Content-Type"] = "application/json";
    var requestOptions = {
      method: options.method || "GET",
      headers: headers,
      body: options.body === undefined ? undefined : JSON.stringify(options.body)
    };
    if (controller) requestOptions.signal = controller.signal;

    return root.fetch(path, requestOptions).then(function (response) {
      return parseBody(response).then(function (payload) {
        if (response.ok) return payload;
        var details = payload && payload.error ? payload.error : {};
        throw makeError("http", details.message || ("Request failed (" + response.status + ")."), {
          status: response.status,
          retryAfter: response.headers.get("Retry-After"),
          details: details,
          classification: details.classification,
          sequence: details.sequence,
          latestSequence: details.latest_sequence
        });
      });
    }).catch(function (error) {
      if (error && error.kind) throw error;
      if (error && error.name === "AbortError") {
        throw makeError("timeout", "The backend request timed out after " + timeoutMs + " ms.");
      }
      throw makeError("network", "The backend is unavailable. No synthetic cloud state was substituted.");
    }).finally(function () {
      root.clearTimeout(timer);
    });
  }

  H.api = {
    request: request,
    isStandalone: function () { return root.location.protocol === "file:"; },
    health: function () { return request("/api/health"); },
    state: function () { return request("/api/state"); },
    stations: function () { return request("/api/stations"); },
    station: function (id) { return request("/api/stations/" + encodeURIComponent(id)); },
    simulate: function (id, scenario) {
      return request("/api/stations/" + encodeURIComponent(id) + "/simulate", {
        method: "POST", body: { scenario: scenario }
      });
    },
    reading: function (id, payload) {
      return request("/api/stations/" + encodeURIComponent(id) + "/readings", {
        method: "POST", body: payload
      });
    },
    fault: function (id, action, payload) {
      return request("/api/stations/" + encodeURIComponent(id) + "/faults/" + encodeURIComponent(action), {
        method: "POST", body: payload || {}
      });
    },
    radioStatus: function () { return request("/api/v2/radio/status"); },
    gatewayHealth: function () { return request("/api/v2/gateway/health"); },
    radioDiagnostics: function (id) {
      return request("/api/v2/stations/" + encodeURIComponent(id) + "/radio-diagnostics");
    }
  };
})(window);
