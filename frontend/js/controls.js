(function (root) {
  "use strict";
  var H = root.HimRakshak = root.HimRakshak || {};
  H.controls = {
    csv: function (rows) {
      var text = "\ufeff" + rows.map(function (row) {
        return row.map(function (value) {
          return '"' + String(value === undefined || value === null ? "" : value).replace(/"/g, '""') + '"';
        }).join(",");
      }).join("\r\n");
      var anchor = document.createElement("a");
      anchor.href = root.URL.createObjectURL(new Blob([text], {type: "text/csv;charset=utf-8"}));
      anchor.download = "himrakshak-events.csv";
      anchor.click();
      root.setTimeout(function () { root.URL.revokeObjectURL(anchor.href); }, 1000);
    }
  };
})(window);
