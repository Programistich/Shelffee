(function () {
  const ROAST_CLASS = { filter: "sf-bag--filter", espresso: "sf-bag--espresso", omni: "sf-bag--omni" };

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  function bagHTML(item, index) {
    return `<button type="button" class="sf-bag ${ROAST_CLASS[item.roast] || ""}" data-index="${index}">
      <span class="sf-bag__name">${esc(item.name)}</span>
      ${item.meta ? `<span class="sf-bag__meta">${esc(item.meta)}</span>` : ""}
    </button>`;
  }

  function shelfHTML(row, offset, label, emptyText) {
    const bags = row.map((item, i) => bagHTML(item, offset + i)).join("");
    return `<div class="sf-shelf${row.length ? "" : " sf-shelf--empty"}">
      <div class="sf-shelf__items">${row.length ? bags : esc(emptyText)}</div>
      <div class="sf-shelf__board"></div>
      ${label ? `<span class="sf-shelf__label">${esc(label)}</span>` : ""}
    </div>`;
  }

  function capacity(rack) {
    const probe = document.createElement("div");
    probe.className = "sf-shelf";
    probe.style.cssText = "position:absolute;left:0;right:0;visibility:hidden;pointer-events:none";
    probe.innerHTML = '<div class="sf-shelf__items"><button type="button" class="sf-bag"></button></div>';
    rack.appendChild(probe);
    const items = probe.firstElementChild;
    const cs = getComputedStyle(items);
    const inner = items.clientWidth - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
    const gap = parseFloat(cs.columnGap) || 0;
    const bag = items.firstElementChild.getBoundingClientRect().width;
    probe.remove();
    return Math.max(1, Math.floor((inner + gap) / (bag + gap)));
  }

  function render(rack, items, opts = {}) {
    const per = capacity(rack);
    const rows = [];
    for (let i = 0; i < items.length; i += per) rows.push(items.slice(i, i + per));
    if (!rows.length) rows.push([]);
    rack.innerHTML = rows.map((row, i) => shelfHTML(row, i * per, i === 0 ? opts.label : null, opts.emptyText || "")).join("");
    rack.dataset.capacity = per;
    if (opts.onSelect) {
      rack.querySelectorAll(".sf-bag").forEach((b) => {
        b.onclick = () => opts.onSelect(items[Number(b.dataset.index)]);
      });
    }
  }

  function mount(rack, items, opts = {}) {
    render(rack, items, opts);
    const ro = new ResizeObserver(() => {
      if (capacity(rack) !== Number(rack.dataset.capacity)) requestAnimationFrame(() => render(rack, items, opts));
    });
    ro.observe(rack);
    return {
      update(next) {
        items = next;
        render(rack, items, opts);
      },
      destroy() {
        ro.disconnect();
      },
    };
  }

  window.SfRack = { mount, render, capacity };
})();
