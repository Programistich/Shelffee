const SfCrop = (() => {
  const MAX_SIDE = 1024;
  const HANDLE = 22;
  const MIN_SIZE = 40;

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => { URL.revokeObjectURL(url); resolve(img); };
      img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Не вдалося відкрити зображення")); };
      img.src = url;
    });
  }

  async function open(file) {
    const img = await loadImage(file);
    return new Promise((resolve) => {
      const box = document.createElement("div");
      box.className = "sf-crop";
      box.innerHTML = `
        <div class="sf-crop__stage"><canvas></canvas></div>
        <p class="sf-hint">Обріжте фото по краях пакета: тягніть кути або рамку</p>
        <div class="sf-row">
          <button class="sf-btn sf-btn--ghost" data-act="cancel" type="button">Скасувати</button>
          <button class="sf-btn" data-act="done" type="button">Готово</button>
        </div>`;
      document.body.append(box);

      const stage = box.querySelector(".sf-crop__stage");
      const canvas = box.querySelector("canvas");
      const ctx = canvas.getContext("2d");
      const dpr = window.devicePixelRatio || 1;
      const scale = Math.min(stage.clientWidth / img.naturalWidth, stage.clientHeight / img.naturalHeight);
      const W = Math.round(img.naturalWidth * scale);
      const H = Math.round(img.naturalHeight * scale);
      canvas.width = W * dpr;
      canvas.height = H * dpr;
      canvas.style.width = `${W}px`;
      canvas.style.height = `${H}px`;
      ctx.scale(dpr, dpr);

      const r = { x1: 0, y1: 0, x2: W, y2: H };
      const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

      function draw() {
        ctx.clearRect(0, 0, W, H);
        ctx.drawImage(img, 0, 0, W, H);
        ctx.fillStyle = "rgba(0,0,0,0.55)";
        ctx.fillRect(0, 0, W, r.y1);
        ctx.fillRect(0, r.y2, W, H - r.y2);
        ctx.fillRect(0, r.y1, r.x1, r.y2 - r.y1);
        ctx.fillRect(r.x2, r.y1, W - r.x2, r.y2 - r.y1);
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.strokeRect(r.x1, r.y1, r.x2 - r.x1, r.y2 - r.y1);
        ctx.fillStyle = "#fff";
        for (const [x, y] of corners()) ctx.fillRect(x - 6, y - 6, 12, 12);
      }

      function corners() {
        return [[r.x1, r.y1], [r.x2, r.y1], [r.x1, r.y2], [r.x2, r.y2]];
      }

      function pos(e) {
        const b = canvas.getBoundingClientRect();
        return { x: clamp(e.clientX - b.left, 0, W), y: clamp(e.clientY - b.top, 0, H) };
      }

      let drag = null;
      canvas.onpointerdown = (e) => {
        const p = pos(e);
        const hit = corners().findIndex(([x, y]) => Math.abs(x - p.x) <= HANDLE && Math.abs(y - p.y) <= HANDLE);
        if (hit >= 0) drag = { corner: hit };
        else if (p.x > r.x1 && p.x < r.x2 && p.y > r.y1 && p.y < r.y2) drag = { move: true, last: p };
        else return;
        canvas.setPointerCapture(e.pointerId);
      };
      canvas.onpointermove = (e) => {
        if (!drag) return;
        const p = pos(e);
        if (drag.move) {
          const w = r.x2 - r.x1, h = r.y2 - r.y1;
          r.x1 = clamp(r.x1 + p.x - drag.last.x, 0, W - w);
          r.y1 = clamp(r.y1 + p.y - drag.last.y, 0, H - h);
          r.x2 = r.x1 + w;
          r.y2 = r.y1 + h;
          drag.last = p;
        } else {
          if (drag.corner % 2 === 0) r.x1 = clamp(p.x, 0, r.x2 - MIN_SIZE);
          else r.x2 = clamp(p.x, r.x1 + MIN_SIZE, W);
          if (drag.corner < 2) r.y1 = clamp(p.y, 0, r.y2 - MIN_SIZE);
          else r.y2 = clamp(p.y, r.y1 + MIN_SIZE, H);
        }
        draw();
      };
      canvas.onpointerup = canvas.onpointercancel = () => { drag = null; };

      function finish(blob) {
        box.remove();
        resolve(blob);
      }

      box.querySelector('[data-act="cancel"]').onclick = () => finish(null);
      box.querySelector('[data-act="done"]').onclick = () => {
        const sx = r.x1 / scale, sy = r.y1 / scale, sw = (r.x2 - r.x1) / scale, sh = (r.y2 - r.y1) / scale;
        const k = Math.min(1, MAX_SIDE / Math.max(sw, sh));
        const out = document.createElement("canvas");
        out.width = Math.round(sw * k);
        out.height = Math.round(sh * k);
        out.getContext("2d").drawImage(img, sx, sy, sw, sh, 0, 0, out.width, out.height);
        out.toBlob(finish, "image/jpeg", 0.85);
      };

      draw();
    });
  }

  return { open };
})();
