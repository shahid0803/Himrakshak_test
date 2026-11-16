(function (root) {
  "use strict";
  var H = root.HimRakshak = root.HimRakshak || {};
  H.q = function (selector, parent) { return (parent || document).querySelector(selector); };
  H.qAll = function (selector, parent) { return Array.prototype.slice.call((parent || document).querySelectorAll(selector)); };
  H.escape = function (value) {
    return String(value === undefined || value === null ? "" : value).replace(/[&<>"']/g, function (character) {
      return {"&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#39;"}[character];
    });
  };
  H.formatTime = function (value) {
    if (!value) return "Unavailable";
    if (value === "SIMULATED") return "SIMULATED";
    var date = new Date(value);
    return isNaN(date.getTime()) ? String(value) : date.toLocaleString();
  };
  H.shell = {
    init: function () {
      var menu = H.q(".menu");
      var sidebar = H.q(".sidebar");
      if (menu && sidebar) menu.addEventListener("click", function () { sidebar.classList.toggle("open"); });
      H.qAll(".nav button").forEach(function (button) {
        button.addEventListener("click", function () { if (sidebar) sidebar.classList.remove("open"); });
      });
    }
  };
})(window);
