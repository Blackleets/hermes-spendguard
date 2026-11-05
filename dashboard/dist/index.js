(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;
  const { useState, useEffect } = React;
  const h = React.createElement;

  function money(x) {
    if (x === null || x === undefined) return "—";
    return "$" + Number(x).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function Bar(p) {
    if (!p.cap) return h("p", { className: "sg-nocap" }, money(p.spent) + " spent · no budget set");
    const pct = Math.min(100, p.pct || 0);
    const cls = p.over ? "sg-bar-over" : pct >= 90 ? "sg-bar-hot" : pct >= 75 ? "sg-bar-warn" : "sg-bar-ok";
    return h("div", null,
      h("div", { className: "sg-bar-row" },
        h("span", null, money(p.spent) + " of " + money(p.cap)),
        h("span", null, (p.pct || 0).toFixed(0) + "%")),
      h("div", { className: "sg-bar" }, h("div", { className: "sg-fill " + cls, style: { width: pct + "%" } })));
  }

  function Period(label, p) {
    return h("section", { className: "sg-card", key: label },
      h("h3", null, label),
      Bar(p),
      h("p", { className: "sg-meta" }, p.calls + " calls · " +
        (p.input_tokens || 0).toLocaleString() + " in / " + (p.output_tokens || 0).toLocaleString() + " out tokens" +
        (p.unpriced ? " · ⚠ " + p.unpriced + " unpriced" : "")));
  }

  function ModelTable(title, rows) {
    if (!rows || !rows.length) return null;
    return h("section", { className: "sg-card", key: title },
      h("h3", null, title),
      h("table", { className: "sg-table" },
        h("thead", null, h("tr", null,
          h("th", null, "Model"), h("th", null, "Spend"), h("th", null, "Calls"))),
        h("tbody", null, rows.map(function (r) {
          return h("tr", { key: r.model || "?" },
            h("td", null, r.model || "(unknown)"),
            h("td", null, money(r.spent)),
            h("td", null, r.calls + (r.unpriced ? " (" + r.unpriced + " unpriced)" : "")));
        }))));
  }

  function SpendGuardPage() {
    const [data, setData] = useState(null);
    const [error, setError] = useState(null);

    useEffect(function () {
      SDK.fetchJSON("/api/plugins/hermes-spendguard/status")
        .then(function (res) { setData(res); })
        .catch(function () { setError("Could not load SpendGuard status."); });
    }, []);

    if (error) return h("div", { className: "sg-page" }, h("h1", null, "💸 SpendGuard"), h("p", null, error));
    if (!data) return h("div", { className: "sg-page" }, h("p", null, "Loading your spend…"));

    const st = data.status;
    const icon = { ok: "🟢", warn: "🟡", over: "🔴", unbudgeted: "⚪" }[st.state] || "";
    return h("div", { className: "sg-page" },
      h("header", { className: "sg-head" },
        h("h1", null, "💸 SpendGuard " + icon),
        h("p", null, st.state === "over"
          ? "Budget reached — new turns are blocked before they reach the model."
          : "Every API call, priced and counted against the budgets only you can set.")),
      Period("Today", st.day),
      Period("This month", st.month),
      ModelTable("Today by model", data.day_by_model),
      ModelTable("This month by model", data.month_by_model),
      h("footer", { className: "sg-foot" },
        "Budgets change only from the /spendguard command — the agent can read its spend, never raise its own cap."));
  }

  window.__HERMES_PLUGINS__.register("hermes-spendguard", SpendGuardPage);
})();
