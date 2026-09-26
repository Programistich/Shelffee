const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const app = document.getElementById("app");
const ROASTS = { filter: "Фільтр", espresso: "Еспресо", omni: "Omni" };
const METHODS = {
  espresso: "Еспресо",
  v60: "V60",
  filter: "Фільтр (пуровер)",
  kalita: "Kalita Wave",
  chemex: "Chemex",
  origami: "Origami",
  hario_switch: "Hario Switch",
  clever: "Clever Dripper",
  aeropress: "AeroPress",
  french_press: "Френч-прес",
  moka: "Мока",
  cezve: "Турка / джезва",
  siphon: "Сифон",
  cold_brew: "Колд брю",
  batch_brew: "Батч брю",
};
let rack = null;

function setRack(next) {
  rack?.destroy();
  rack = next;
}

if (tg.colorScheme === "dark") document.documentElement.dataset.theme = "evening";

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: {
      Authorization: `tma ${tg.initData}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!res.ok) throw new Error(await res.text());
  return res.status === 204 ? null : res.json();
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function showError(e) {
  const el = document.createElement("p");
  el.className = "sf-error";
  el.textContent = e.message || String(e);
  app.prepend(el);
}

function confirmAction(message) {
  return new Promise((resolve) => {
    if (tg.isVersionAtLeast?.("6.2")) tg.showConfirm(message, resolve);
    else resolve(window.confirm(message));
  });
}

function setBack(handler) {
  tg.BackButton.offClick(setBack.current);
  setBack.current = handler;
  if (handler) {
    tg.BackButton.onClick(handler);
    tg.BackButton.show();
  } else {
    tg.BackButton.hide();
  }
}

async function showShelves() {
  setBack(null);
  setRack(null);
  const shelves = await api("/shelves");
  app.innerHTML = `
    <h1>Мої полиці</h1>
    <ul class="sf-list sf-card">
      ${shelves.map((s) => `<li data-id="${s.id}">${esc(s.name)}</li>`).join("")}
    </ul>
    ${shelves.length ? "" : '<p class="sf-hint">Полиць ще немає — створіть першу.</p>'}
    <form id="new-shelf" class="sf-row">
      <input class="sf-field" name="name" placeholder="Назва полиці" required>
      <button class="sf-btn" type="submit">Створити</button>
    </form>
  `;
  app.querySelectorAll("li").forEach((li) => li.onclick = () => showShelf(Number(li.dataset.id)));
  app.querySelector("#new-shelf").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const shelf = await api("/shelves", { method: "POST", body: JSON.stringify({ name: e.target.name.value }) });
      showShelf(shelf.id);
    } catch (err) { showError(err); }
  };
}

async function showShelf(shelfId) {
  setBack(showShelves);
  const { shelf, role, coffees } = await api(`/shelves/${shelfId}/coffees`);
  app.innerHTML = `
    <h1>${esc(shelf.name)}</h1>
    <div class="sf-row">
      <button id="edit" class="sf-btn sf-btn--ghost">Редагувати</button>
      <button id="share" class="sf-btn sf-btn--ghost">Поділитися</button>
      <button id="add" class="sf-btn">Додати каву</button>
    </div>
    <div id="rack" class="sf-rack"></div>
  `;
  setRack(SfRack.mount(
    app.querySelector("#rack"),
    coffees.map((c) => ({ id: c.id, name: c.name, meta: `${c.weight_grams} г · ${c.country}`, roast: c.roast })),
    { emptyText: "На полиці ще порожньо", onSelect: (c) => showCoffee(c.id, shelfId) },
  ));
  app.querySelector("#add").onclick = () => showCoffeeForm(shelfId);
  app.querySelector("#edit").onclick = () => showShelfForm(shelf, role);
  app.querySelector("#share").onclick = async () => {
    try {
      const { link } = await api(`/shelves/${shelfId}/share`);
      tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(`Приєднуйся до полиці «${shelf.name}» у Shelffee`)}`);
    } catch (err) { showError(err); }
  };
}

function showShelfForm(shelf, role) {
  setBack(() => showShelf(shelf.id));
  setRack(null);
  app.innerHTML = `
    <h1>Полиця</h1>
    <form id="shelf" class="sf-form sf-card">
      <input class="sf-field" name="name" placeholder="Назва полиці" value="${esc(shelf.name)}" required>
      <button class="sf-btn" type="submit">Зберегти</button>
    </form>
    ${role === "owner" ? '<button id="delete" class="sf-btn sf-btn--danger">Видалити полицю</button>' : ""}
  `;
  app.querySelector("#shelf").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api(`/shelves/${shelf.id}`, { method: "PUT", body: JSON.stringify({ name: e.target.name.value }) });
      showShelf(shelf.id);
    } catch (err) { showError(err); }
  };
  const del = app.querySelector("#delete");
  if (del) del.onclick = async () => {
    if (!(await confirmAction(`Видалити полицю «${shelf.name}» разом з усією кавою?`))) return;
    try {
      await api(`/shelves/${shelf.id}`, { method: "DELETE" });
      showShelves();
    } catch (err) { showError(err); }
  };
}

function showCoffeeForm(shelfId, coffee = null) {
  setBack(() => (coffee ? showCoffee(coffee.id, shelfId) : showShelf(shelfId)));
  setRack(null);
  const v = (k) => esc(coffee?.[k] ?? "");
  const sel = (k, val) => (String(coffee?.[k] ?? "") === String(val) ? " selected" : "");
  app.innerHTML = `
    <h1>${coffee ? "Редагувати каву" : "Нова кава"}</h1>
    <form id="coffee" class="sf-form sf-card">
      <input class="sf-field" name="name" placeholder="Назва" value="${v("name")}" required>
      <input class="sf-field" name="country" placeholder="Країна" value="${v("country")}" required>
      <input class="sf-field" name="flavor_notes" placeholder="Дескриптори смаку, через кому" value="${esc((coffee?.flavor_notes || []).join(", "))}" required>
      <select class="sf-field" name="roast" required>
        ${Object.entries(ROASTS).map(([val, l]) => `<option value="${val}"${sel("roast", val)}>${l}</option>`).join("")}
      </select>
      <div class="sf-grid2">
        <input class="sf-field" name="weight_grams" type="number" min="1" placeholder="Вага, г" value="${v("weight_grams")}" required>
        <input class="sf-field" name="process" placeholder="Метод обробки" value="${v("process")}" required>
      </div>
      <fieldset>
        <legend class="sf-hint">Необов'язково</legend>
        <input class="sf-field" name="region" placeholder="Регіон" value="${v("region")}">
        <input class="sf-field" name="variety" placeholder="Різновид / сорт" value="${v("variety")}">
        <div class="sf-grid2">
          <input class="sf-field" name="altitude_masl" type="number" min="0" placeholder="Висота, MASL" value="${v("altitude_masl")}">
          <input class="sf-field" name="farm" placeholder="Ферма / станція" value="${v("farm")}">
        </div>
        <select class="sf-field" name="sensory_scale">
          <option value="">Сенсорна шкала — немає</option>
          <option value="5"${sel("sensory_scale", 5)}>Шкала /5</option>
          <option value="10"${sel("sensory_scale", 10)}>Шкала /10</option>
        </select>
        <div class="sf-grid2">
          <input class="sf-field" name="acidity" type="number" min="0" placeholder="Кислотність" value="${v("acidity")}">
          <input class="sf-field" name="sweetness" type="number" min="0" placeholder="Солодкість" value="${v("sweetness")}">
          <input class="sf-field" name="bitterness" type="number" min="0" placeholder="Гіркота" value="${v("bitterness")}">
          <input class="sf-field" name="body" type="number" min="0" placeholder="Тіло" value="${v("body")}">
        </div>
      </fieldset>
      <button class="sf-btn" type="submit">Зберегти</button>
    </form>
  `;
  app.querySelector("#coffee").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const str = (k) => f.get(k).trim() || null;
    const num = (k) => (f.get(k) === "" ? null : Number(f.get(k)));
    const body = {
      name: str("name"),
      country: str("country"),
      flavor_notes: f.get("flavor_notes").split(",").map((s) => s.trim()).filter(Boolean),
      roast: f.get("roast"),
      weight_grams: num("weight_grams"),
      process: str("process"),
      region: str("region"),
      variety: str("variety"),
      altitude_masl: num("altitude_masl"),
      farm: str("farm"),
      sensory_scale: num("sensory_scale"),
      acidity: num("acidity"),
      sweetness: num("sweetness"),
      bitterness: num("bitterness"),
      body: num("body"),
    };
    try {
      const saved = coffee
        ? await api(`/coffees/${coffee.id}`, { method: "PUT", body: JSON.stringify(body) })
        : await api(`/shelves/${shelfId}/coffees`, { method: "POST", body: JSON.stringify(body) });
      showCoffee(saved.id, shelfId);
    } catch (err) { showError(err); }
  };
}

async function showCoffee(coffeeId, shelfId) {
  setBack(() => showShelf(shelfId));
  setRack(null);
  const c = await api(`/coffees/${coffeeId}`);
  const score = (v) => (v == null ? null : c.sensory_scale ? `${v}/${c.sensory_scale}` : String(v));
  const meter = (label, v) => (v == null || !c.sensory_scale ? "" : `
    <div class="sf-meter"><span>${label}</span><div class="sf-meter__track"><div class="sf-meter__fill" style="width:${Math.min(100, (v / c.sensory_scale) * 100)}%"></div></div></div>`);
  const rows = [
    ["Країна", c.country],
    ["Регіон", c.region],
    ["Ферма / станція", c.farm],
    ["Висота", c.altitude_masl == null ? null : `${c.altitude_masl} MASL`],
    ["Різновид", c.variety],
    ["Обробка", c.process],
    ["Обсмажка", ROASTS[c.roast]],
    ["Вага", `${c.weight_grams} г`],
    ...(c.sensory_scale ? [] : [
      ["Кислотність", score(c.acidity)],
      ["Солодкість", score(c.sweetness)],
      ["Гіркота", score(c.bitterness)],
      ["Тіло", score(c.body)],
    ]),
  ].filter(([, v]) => v != null && v !== "");
  app.innerHTML = `
    <h1>${esc(c.name)}</h1>
    <div class="sf-card">
      <p style="margin:0 0 12px">${c.flavor_notes.map((n) => `<span class="sf-tag">${esc(n)}</span>`).join(" ")}</p>
      <dl class="sf-dl">${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join("")}</dl>
      ${c.sensory_scale ? `<div style="margin-top:12px">${meter("Кислотність", c.acidity)}${meter("Солодкість", c.sweetness)}${meter("Гіркота", c.bitterness)}${meter("Тіло", c.body)}</div>` : ""}
    </div>
    <div class="sf-row">
      <button id="edit" class="sf-btn sf-btn--ghost">Редагувати</button>
      <button id="delete" class="sf-btn sf-btn--danger">Видалити</button>
    </div>
    <h2>Рецепти</h2>
    ${c.recipes.length ? `<ul class="sf-list sf-card">${c.recipes.map((r) => `
      <li>
        <strong>${METHODS[r.method] || esc(r.method)}</strong> · ${r.dose_grams} г${r.grind ? ` · ${esc(r.grind)}` : ""}
        ${r.notes ? `<div class="sf-hint">${esc(r.notes)}</div>` : ""}
      </li>`).join("")}</ul>` : '<p class="sf-hint">Рецептів ще немає.</p>'}
    <form id="recipe" class="sf-form sf-card">
      <select class="sf-field" name="method" required>
        ${Object.entries(METHODS).map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}
      </select>
      <div class="sf-grid2">
        <input class="sf-field" name="dose_grams" type="number" min="0.1" step="0.1" placeholder="Доза, г" required>
        <input class="sf-field" name="grind" placeholder="Помел">
      </div>
      <textarea class="sf-field" name="notes" rows="3" placeholder="Нотатки"></textarea>
      <button class="sf-btn" type="submit">Додати рецепт</button>
    </form>
  `;
  app.querySelector("#edit").onclick = () => showCoffeeForm(shelfId, c);
  app.querySelector("#delete").onclick = async () => {
    if (!(await confirmAction(`Видалити «${c.name}»?`))) return;
    try {
      await api(`/coffees/${coffeeId}`, { method: "DELETE" });
      showShelf(shelfId);
    } catch (err) { showError(err); }
  };
  app.querySelector("#recipe").onsubmit = async (e) => {
    e.preventDefault();
    const f = new FormData(e.target);
    const body = {
      method: f.get("method"),
      dose_grams: Number(f.get("dose_grams")),
      grind: f.get("grind").trim() || null,
      notes: f.get("notes").trim() || null,
    };
    try {
      await api(`/coffees/${coffeeId}/recipes`, { method: "POST", body: JSON.stringify(body) });
      showCoffee(coffeeId, shelfId);
    } catch (err) { showError(err); }
  };
}

showShelves().catch(showError);
