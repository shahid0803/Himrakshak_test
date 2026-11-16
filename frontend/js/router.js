(function (root) {
  "use strict";
  var H = root.HimRakshak = root.HimRakshak || {};
  var routes = ["overview", "stations", "live-monitoring", "lora-network", "simulation-lab", "alerts-events", "diagnostics"];
  function current() {
    var route = (root.location.hash || "#overview").slice(1);
    return routes.indexOf(route) >= 0 ? route : "overview";
  }
  function go(route) {
    root.location.hash = routes.indexOf(route) >= 0 ? route : "overview";
  }
  H.router = {
    current: current,
    go: go,
    init: function (onChange) {
      root.addEventListener("hashchange", function () { onChange(current()); });
      H.qAll("[data-route]").forEach(function (button) {
        button.addEventListener("click", function () { go(button.getAttribute("data-route")); });
      });
      onChange(current());
    }
  };
})(window);
