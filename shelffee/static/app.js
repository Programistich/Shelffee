const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

const inTelegram = Boolean(tg.initData);
const app = document.getElementById("app");
const backBtn = document.getElementById("back");
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
let racks = [];

function setRack(next) {
  racks.forEach((r) => r.destroy());
  racks = next ? [next] : [];
}

function addRack(r) {
  racks.push(r);
}

const isDark = inTelegram ? tg.colorScheme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
if (isDark) document.documentElement.dataset.theme = "evening";

function authHeaders() {
  return inTelegram ? { Authorization: `tma ${tg.initData}` } : {};
}

async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    ...options,
    headers: {
      ...authHeaders(),
      ...(options.body instanceof FormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401 && !inTelegram) showLogin();
  if (!res.ok) throw new Error(await res.text());
  return res.status === 204 ? null : res.json();
}

function showPhoto(img) {
  img.hidden = false;
  img.onclick = () => {
    const box = document.createElement("div");
    box.className = "sf-lightbox";
    box.innerHTML = `<img src="${img.src}" alt="">`;
    box.onclick = () => box.remove();
    document.body.append(box);
  };
}

async function loadPhoto(img, coffeeId) {
  try {
    const res = await fetch(`/api/coffees/${coffeeId}/photo`, { headers: authHeaders() });
    if (!res.ok) return;
    img.src = URL.createObjectURL(await res.blob());
    showPhoto(img);
  } catch {}
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
  if (!inTelegram) {
    backBtn.hidden = !handler;
    backBtn.onclick = handler;
    return;
  }
  tg.BackButton.offClick(setBack.current);
  setBack.current = handler;
  if (handler) {
    tg.BackButton.onClick(handler);
    tg.BackButton.show();
  } else {
    tg.BackButton.hide();
  }
}

function showLogin() {
  setBack(null);
  setRack(null);
  app.innerHTML = `
    <h1>Shelffee</h1>
    <div class="sf-login">
      <p class="sf-hint">Увійдіть через Telegram, щоб бачити свої полиці.</p>
      <div id="tg-login"></div>
    </div>
  `;
  const script = document.createElement("script");
  script.src = "https://telegram.org/js/telegram-widget.js?22";
  script.async = true;
  script.dataset.telegramLogin = document.body.dataset.bot;
  script.dataset.size = "large";
  script.dataset.authUrl = `${location.origin}/auth/telegram`;
  script.dataset.requestAccess = "write";
  app.querySelector("#tg-login").append(script);
}

async function logout() {
  await fetch("/auth/logout", { method: "POST" });
  showLogin();
}

async function showShelves() {
  setBack(null);
  setRack(null);
  const shelves = await api("/shelves");
  app.innerHTML = `
    <h1>Мої полиці</h1>
    ${shelves.map((s) => `
      <section class="sf-shelf-block" data-id="${s.id}">
        <div class="sf-shelf-head">
          <button type="button" class="sf-shelf-name" data-open>${esc(s.name)}<span class="sf-shelf-name__chevron">›</span></button>
          <button type="button" class="sf-btn sf-btn--ghost sf-btn--sm" data-add>+ Кава</button>
        </div>
        <div class="sf-rack" data-rack></div>
      </section>`).join("")}
    ${shelves.length ? "" : '<p class="sf-hint">Полиць ще немає — створіть першу.</p>'}
    <form id="new-shelf" class="sf-row">
      <input class="sf-field" name="name" placeholder="Нова полиця" required>
      <button class="sf-btn" type="submit">Створити</button>
    </form>
    ${inTelegram ? "" : '<p><button id="logout" class="sf-btn sf-btn--ghost sf-btn--sm" type="button">Вийти</button></p>'}
  `;
  const logoutBtn = app.querySelector("#logout");
  if (logoutBtn) logoutBtn.onclick = () => logout().catch(showError);
  shelves.forEach((s) => {
    const block = app.querySelector(`.sf-shelf-block[data-id="${s.id}"]`);
    addRack(SfRack.mount(
      block.querySelector("[data-rack]"),
      s.coffees.map((c) => ({ id: c.id, name: c.name, meta: `${c.weight_grams} г · ${c.country}`, roast: c.roast })),
      { emptyText: "Порожньо", onSelect: (c) => showCoffee(c.id) },
    ));
    block.querySelector("[data-open]").onclick = () => showShelfForm(s, s.role);
    block.querySelector("[data-add]").onclick = () => showCoffeeForm(s.id);
  });
  app.querySelector("#new-shelf").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api("/shelves", { method: "POST", body: JSON.stringify({ name: e.target.name.value }) });
      showShelves();
    } catch (err) { showError(err); }
  };
}

function showShelfForm(shelf, role) {
  setBack(showShelves);
  setRack(null);
  app.innerHTML = `
    <h1>Полиця</h1>
    <form id="shelf" class="sf-form sf-card">
      <input class="sf-field" name="name" placeholder="Назва полиці" value="${esc(shelf.name)}" required>
      <button class="sf-btn" type="submit">Зберегти</button>
    </form>
    <div class="sf-row">
      <button id="share" class="sf-btn sf-btn--ghost">Поділитися</button>
      ${role === "owner" ? '<button id="delete" class="sf-btn sf-btn--danger">Видалити полицю</button>' : ""}
    </div>
  `;
  app.querySelector("#shelf").onsubmit = async (e) => {
    e.preventDefault();
    try {
      await api(`/shelves/${shelf.id}`, { method: "PUT", body: JSON.stringify({ name: e.target.name.value }) });
      showShelves();
    } catch (err) { showError(err); }
  };
  app.querySelector("#share").onclick = async () => {
    try {
      const { link } = await api(`/shelves/${shelf.id}/share`);
      const shareUrl = `https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent(`Приєднуйся до полиці «${shelf.name}» у Shelffee`)}`;
      if (inTelegram) tg.openTelegramLink(shareUrl);
      else window.open(shareUrl, "_blank");
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
  setBack(() => (coffee ? showCoffee(coffee.id) : showShelves()));
  setRack(null);
  const v = (k) => esc(coffee?.[k] ?? "");
  const sel = (k, val) => (String(coffee?.[k] ?? "") === String(val) ? " selected" : "");
  app.innerHTML = `
    <h1>${coffee ? "Редагувати каву" : "Нова кава"}</h1>
    <form id="coffee" class="sf-form sf-card">
      <input id="photo" type="file" accept="image/*" capture="environment" hidden>
      <div class="sf-photo-row">
        <img id="preview" class="sf-photo" alt="" hidden>
        <div>
          <button id="scan" class="sf-btn sf-btn--ghost" type="button">Заповнити з фото</button>
          <p id="scan-hint" class="sf-hint" hidden>Поля заповнено з фото — перевірте й виправте за потреби, потім збережіть.</p>
        </div>
      </div>
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
  const form = app.querySelector("#coffee");
  const photo = app.querySelector("#photo");
  const scan = app.querySelector("#scan");
  const preview = app.querySelector("#preview");
  let photoData = null;
  if (coffee?.has_photo) loadPhoto(preview, coffee.id);
  scan.onclick = () => photo.click();
  photo.onchange = async () => {
    const file = photo.files[0];
    photo.value = "";
    if (!file) return;
    let cropped;
    try { cropped = await SfCrop.open(file); } catch (err) { showError(err); return; }
    if (!cropped) return;
    const body = new FormData();
    body.append("image", cropped, "photo.jpg");
    scan.disabled = true;
    scan.textContent = "Розпізнаю…";
    try {
      const r = await api("/coffees/recognize", { method: "POST", body });
      const set = (k, val) => { if (val != null && val !== "") form.elements[k].value = val; };
      set("name", r.roaster && r.name ? `${r.roaster} ${r.name}` : r.name || r.roaster);
      set("country", r.country);
      set("flavor_notes", r.flavor_notes.join(", "));
      set("roast", r.roast);
      set("weight_grams", r.weight_grams);
      set("process", r.process);
      set("region", r.region);
      set("variety", r.variety);
      set("altitude_masl", r.altitude_masl);
      set("farm", r.farm);
      set("sensory_scale", r.sensory_scale);
      set("acidity", r.acidity);
      set("sweetness", r.sweetness);
      set("bitterness", r.bitterness);
      set("body", r.body);
      photoData = r.photo;
      preview.src = `data:image/jpeg;base64,${r.photo}`;
      showPhoto(preview);
      app.querySelector("#scan-hint").hidden = false;
      form.elements.name.focus();
    } catch (err) { showError(err); }
    finally {
      scan.disabled = false;
      scan.textContent = "Заповнити з фото";
    }
  };
  form.onsubmit = async (e) => {
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
      ...(photoData ? { photo: photoData } : {}),
    };
    try {
      const saved = coffee
        ? await api(`/coffees/${coffee.id}`, { method: "PUT", body: JSON.stringify(body) })
        : await api(`/shelves/${shelfId}/coffees`, { method: "POST", body: JSON.stringify(body) });
      showCoffee(saved.id);
    } catch (err) { showError(err); }
  };
}

async function showCoffee(coffeeId) {
  setBack(showShelves);
  setRack(null);
  const c = await api(`/coffees/${coffeeId}`);
  const meter = (label, v) => (v == null || !c.sensory_scale ? "" : `
    <div class="sf-meter"><span>${label}</span><div class="sf-meter__track"><div class="sf-meter__fill" style="width:${Math.min(100, (v / c.sensory_scale) * 100)}%"></div></div></div>`);
  const facts = [
    ["Обробка", c.process],
    ["Різновид", c.variety],
    ["Ферма / станція", c.farm],
    ["Висота", c.altitude_masl == null ? null : `${c.altitude_masl} MASL`],
    ...(c.sensory_scale ? [] : [
      ["Кислотність", c.acidity],
      ["Солодкість", c.sweetness],
      ["Гіркота", c.bitterness],
      ["Тіло", c.body],
    ]),
  ].filter(([, v]) => v != null && v !== "");
  app.innerHTML = `
    <div class="sf-card sf-coffee">
      <div class="sf-coffee__head">
        <img id="photo" class="sf-photo" alt="" hidden>
        <div>
          <h1 class="sf-coffee__name">${esc(c.name)}</h1>
          <p class="sf-hint sf-coffee__origin">${esc([c.country, c.region].filter(Boolean).join(" · "))}</p>
          <p class="sf-coffee__chips">
            <span class="sf-chip sf-chip--${c.roast}">${ROASTS[c.roast]}</span>
            <span class="sf-chip">${c.weight_grams} г</span>
          </p>
        </div>
      </div>
      <p class="sf-coffee__tags">${c.flavor_notes.map((n) => `<span class="sf-tag">${esc(n)}</span>`).join(" ")}</p>
      ${facts.length ? `<div class="sf-facts">${facts.map(([k, v]) => `<div><span class="sf-facts__k">${k}</span><span class="sf-facts__v">${esc(v)}</span></div>`).join("")}</div>` : ""}
      ${c.sensory_scale ? `<div class="sf-coffee__meters">${meter("Кислотність", c.acidity)}${meter("Солодкість", c.sweetness)}${meter("Гіркота", c.bitterness)}${meter("Тіло", c.body)}</div>` : ""}
    </div>
    <div class="sf-row">
      <button id="edit" class="sf-btn sf-btn--ghost">Редагувати</button>
      <button id="delete" class="sf-btn sf-btn--ghost sf-btn--danger-ghost">Видалити</button>
    </div>
    <h2>Рецепти</h2>
    ${c.recipes.length ? `<ul class="sf-list sf-card">${c.recipes.map((r) => `
      <li>
        <div>
          <strong>${METHODS[r.method] || esc(r.method)}</strong> · ${r.dose_grams} г${r.grind ? ` · ${esc(r.grind)}` : ""}
          ${r.notes ? `<div class="sf-hint">${esc(r.notes)}</div>` : ""}
        </div>
      </li>`).join("")}</ul>` : '<p class="sf-hint">Рецептів ще немає.</p>'}
    <button id="add-recipe" class="sf-btn sf-btn--ghost">Додати рецепт</button>
    <form id="recipe" class="sf-form sf-card" hidden>
      <select class="sf-field" name="method" required>
        ${Object.entries(METHODS).map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}
      </select>
      <div class="sf-grid2">
        <input class="sf-field" name="dose_grams" type="number" min="0.1" step="0.1" placeholder="Доза, г" required>
        <input class="sf-field" name="grind" placeholder="Помел">
      </div>
      <textarea class="sf-field" name="notes" rows="3" placeholder="Нотатки"></textarea>
      <button class="sf-btn" type="submit">Зберегти рецепт</button>
    </form>
  `;
  if (c.has_photo) loadPhoto(app.querySelector("#photo"), c.id);
  app.querySelector("#edit").onclick = () => showCoffeeForm(c.shelf_id, c);
  app.querySelector("#delete").onclick = async () => {
    if (!(await confirmAction(`Видалити «${c.name}»?`))) return;
    try {
      await api(`/coffees/${coffeeId}`, { method: "DELETE" });
      showShelves();
    } catch (err) { showError(err); }
  };
  const recipeForm = app.querySelector("#recipe");
  const addRecipe = app.querySelector("#add-recipe");
  addRecipe.onclick = () => {
    recipeForm.hidden = false;
    addRecipe.hidden = true;
    recipeForm.elements.dose_grams.focus();
  };
  recipeForm.onsubmit = async (e) => {
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
      showCoffee(coffeeId);
    } catch (err) { showError(err); }
  };
}

(async () => {
  if (!inTelegram && !(await fetch("/api/me")).ok) return showLogin();
  await showShelves();
})().catch(showError);
