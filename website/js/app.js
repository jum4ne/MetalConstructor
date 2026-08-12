/* =========================================================================
   TERRASA — общая логика многостраничного сайта.
   Один и тот же app.js подключается на всех страницах; каждая функция
   включается только если на странице есть нужные элементы.
   ========================================================================= */
(function () {
  "use strict";
  const S = window.SITE || {};
  const $  = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));
  const fmt = (n) => new Intl.NumberFormat("ru-RU").format(Math.round(n)) + " " + (S.currency || "₽");
  const esc = (s) => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  /* =======================================================================
     ГРАДИЕНТЫ (нержавейка + огонь)
     ======================================================================= */
  (function injectDefs() {
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    defs.setAttribute("width", "0"); defs.setAttribute("height", "0");
    defs.setAttribute("aria-hidden", "true");
    defs.style.cssText = "position:absolute;width:0;height:0";
    defs.innerHTML = `<defs>
      <linearGradient id="steelGrad" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#dfe7f0"/><stop offset=".25" stop-color="#a7b4c6"/>
        <stop offset=".5" stop-color="#eef3f8"/><stop offset=".72" stop-color="#93a1b4"/>
        <stop offset="1" stop-color="#c6d0dd"/>
      </linearGradient>
      <linearGradient id="steelDark" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stop-color="#9fadbf"/><stop offset=".5" stop-color="#c2ccd9"/>
        <stop offset="1" stop-color="#7d8b9e"/>
      </linearGradient>
      <linearGradient id="emberGrad" x1="0" y1="1" x2="0" y2="0">
        <stop offset="0" stop-color="#d98b39"/><stop offset="1" stop-color="#ffe0a0"/>
      </linearGradient>
    </defs>`;
    (document.body || document.documentElement).appendChild(defs);
  })();

  /* =======================================================================
     ШРИФТЫ (Manrope + Inter, с системным фолбэком — сайт работает и офлайн)
     ======================================================================= */
  (function injectFonts() {
    const head = document.head;
    const pre1 = document.createElement("link"); pre1.rel = "preconnect"; pre1.href = "https://fonts.googleapis.com";
    const pre2 = document.createElement("link"); pre2.rel = "preconnect"; pre2.href = "https://fonts.gstatic.com"; pre2.crossOrigin = "anonymous";
    const css = document.createElement("link"); css.rel = "stylesheet";
    css.href = "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap";
    head.appendChild(pre1); head.appendChild(pre2); head.appendChild(css);
  })();

  /* =======================================================================
     ИКОНКИ
     ======================================================================= */
  const ICON = {
    weather: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M7 18a4 4 0 0 1 0-8 5 5 0 0 1 9.6-1.3A3.5 3.5 0 0 1 18 18Z"/><path d="M8 21l-1 1M12 21l-1 1M16 21l-1 1"/></svg>`,
    fire: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3s5 3.5 5 8a5 5 0 0 1-10 0c0-1.5.6-2.7 1.2-3.5C8.8 8.9 9 10 10 10.5 10 8 12 6 12 3Z"/></svg>`,
    hygiene: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6v4l-1 1v3l3 8H7l3-8V8L9 7Z"/><path d="M9 13h6"/></svg>`,
    modular: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="8" height="8" rx="1"/><rect x="13" y="3" width="8" height="8" rx="1"/><rect x="3" y="13" width="8" height="8" rx="1"/><rect x="13" y="13" width="8" height="8" rx="1"/></svg>`,
    weld: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21l7-7"/><path d="M14 3l7 7-4 4-7-7Z"/><path d="M11 6l3 3"/></svg>`,
    shield: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l8 3v5c0 5-3.5 8.5-8 10-4.5-1.5-8-5-8-10V6Z"/><path d="m9 12 2 2 4-4"/></svg>`,
    phone: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l2 5-3 2a12 12 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z"/></svg>`,
    mail: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>`,
    whatsapp: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2a10 10 0 0 0-8.7 15l-1.3 5 5.1-1.3A10 10 0 1 0 12 2Zm5.8 14.2c-.2.7-1.4 1.3-2 1.4-.5.1-1.2.1-1.9-.1-.4-.1-1-.3-1.7-.6-3-1.3-4.9-4.3-5-4.5-.2-.2-1.2-1.6-1.2-3s.7-2.1 1-2.4c.2-.3.5-.4.7-.4h.5c.2 0 .4 0 .6.5l.8 2c.1.2.1.4 0 .5l-.4.6-.3.3c-.2.2-.3.4-.2.7.2.3.8 1.4 1.8 2.2 1.2 1.1 2.2 1.4 2.5 1.6.2.1.4.1.6-.1l.7-.9c.2-.3.4-.2.6-.1l2 1c.3.1.4.2.5.3.1.3.1.7-.1 1.3Z"/></svg>`,
    telegram: `<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21.9 4.3 18.6 20c-.2 1-.9 1.3-1.8.8l-5-3.7-2.4 2.3c-.3.3-.5.5-1 .5l.3-5 9.1-8.2c.4-.3-.1-.5-.6-.2L6.1 13.4l-4.8-1.5c-1-.3-1-.9.2-1.4L20.5 3c.9-.3 1.6.2 1.4 1.3Z"/></svg>`,
    clock: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>`,
    pin: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 21s7-6 7-11a7 7 0 1 0-14 0c0 5 7 11 7 11Z"/><circle cx="12" cy="10" r="2.5"/></svg>`,
  };

  /* =======================================================================
     SVG-ИЛЛЮСТРАЦИИ МОДУЛЕЙ
     ======================================================================= */
  const legs = (m) => m
    ? `<circle cx="34" cy="140" r="8" fill="#20262f" stroke="url(#steelDark)" stroke-width="2"/><circle cx="166" cy="140" r="8" fill="#20262f" stroke="url(#steelDark)" stroke-width="2"/>`
    : `<rect x="30" y="132" width="10" height="12" rx="2" fill="url(#steelDark)"/><rect x="160" y="132" width="10" height="12" rx="2" fill="url(#steelDark)"/>`;
  const frame = (m) => `<rect x="28" y="34" width="144" height="100" rx="4" fill="none" stroke="url(#steelDark)" stroke-width="3"/>${legs(m)}`;
  const top = `<rect x="22" y="28" width="156" height="12" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e" stroke-width="1"/>`;

  const ART = {
    drawers: (m) => `<svg viewBox="0 0 200 150">${frame(m)}<rect x="34" y="42" width="132" height="86" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/>${[0,1,2,3].map(i=>`<rect x="42" y="${48+i*20}" width="116" height="15" rx="2" fill="none" stroke="#8794a6" stroke-width="1.5"/><rect x="86" y="${52+i*20}" width="28" height="4" rx="2" fill="#5a6675"/>`).join("")}${top}</svg>`,
    doors: (m) => `<svg viewBox="0 0 200 150">${frame(m)}<rect x="34" y="42" width="132" height="86" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/><line x1="100" y1="46" x2="100" y2="124" stroke="#8794a6" stroke-width="1.5"/><rect x="90" y="80" width="4" height="18" rx="2" fill="#5a6675"/><rect x="106" y="80" width="4" height="18" rx="2" fill="#5a6675"/>${top}</svg>`,
    sink: (m) => `<svg viewBox="0 0 200 150">${frame(m)}<rect x="34" y="42" width="132" height="86" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/><line x1="100" y1="60" x2="100" y2="124" stroke="#8794a6" stroke-width="1.2"/><rect x="22" y="24" width="156" height="14" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/><rect x="120" y="28" width="34" height="7" rx="3.5" fill="none" stroke="#5a6675" stroke-width="2"/><path d="M62 20c0-6 6-6 6-2v11" fill="none" stroke="url(#emberGrad)" stroke-width="3" stroke-linecap="round"/><ellipse cx="52" cy="31" rx="12" ry="4" fill="#2a323f" stroke="#5a6675"/></svg>`,
    grill: (m) => `<svg viewBox="0 0 200 150"><rect x="28" y="40" width="144" height="94" rx="4" fill="none" stroke="url(#steelDark)" stroke-width="3"/>${legs(m)}<rect x="34" y="48" width="132" height="80" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/><rect x="42" y="22" width="116" height="20" rx="3" fill="#1a1f27" stroke="#5a6675"/>${[0,1,2,3,4].map(i=>`<circle cx="${54+i*24}" cy="32" r="2.4" fill="url(#emberGrad)"/>`).join("")}${[0,1,2,3,4].map(i=>`<line x1="${52+i*24}" y1="24" x2="${52+i*24}" y2="40" stroke="#8794a6" stroke-width="1.5"/>`).join("")}<path d="M74 20c-3-4 1-7-1-10 4 2 5 6 3 9M100 18c-3-5 1-8-1-11 5 3 5 7 3 10M126 20c-3-4 1-7-1-10 4 2 5 6 3 9" fill="none" stroke="url(#emberGrad)" stroke-width="2.4" stroke-linecap="round"/><rect x="86" y="98" width="28" height="4" rx="2" fill="#5a6675"/></svg>`,
    hood: (m) => `<svg viewBox="0 0 200 150"><rect x="88" y="8" width="24" height="34" fill="url(#steelGrad)" stroke="#7d8b9e"/><path d="M40 92 L74 42 H126 L160 92 Z" fill="url(#steelGrad)" stroke="#7d8b9e" stroke-width="1.5"/><path d="M40 92 H160 V104 H40 Z" fill="url(#steelDark)" stroke="#7d8b9e"/><line x1="70" y1="60" x2="130" y2="60" stroke="#8794a6" stroke-width="1"/><rect x="70" y="118" width="60" height="8" rx="2" fill="none" stroke="url(#steelDark)" stroke-width="2"/></svg>`,
    table: (m) => `<svg viewBox="0 0 200 150"><rect x="26" y="40" width="148" height="96" rx="4" fill="none" stroke="url(#steelDark)" stroke-width="3"/>${m?`<circle cx="34" cy="142" r="8" fill="#20262f" stroke="url(#steelDark)" stroke-width="2"/><circle cx="166" cy="142" r="8" fill="#20262f" stroke="url(#steelDark)" stroke-width="2"/>`:""}<line x1="32" y1="112" x2="168" y2="112" stroke="url(#steelDark)" stroke-width="3"/><rect x="20" y="30" width="160" height="13" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/></svg>`,
    shelf: (m) => `<svg viewBox="0 0 200 150"><rect x="34" y="24" width="132" height="120" rx="4" fill="none" stroke="url(#steelDark)" stroke-width="3"/><rect x="40" y="24" width="120" height="10" rx="2" fill="url(#steelGrad)" stroke="#7d8b9e"/><rect x="40" y="72" width="120" height="9" rx="2" fill="url(#steelGrad)" stroke="#7d8b9e"/><rect x="40" y="116" width="120" height="9" rx="2" fill="url(#steelGrad)" stroke="#7d8b9e"/></svg>`,
    apron: (m) => `<svg viewBox="0 0 200 150"><rect x="30" y="20" width="140" height="90" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/>${[0,1,2,3,4].map(i=>`<line x1="${44+i*28}" y1="26" x2="${44+i*28}" y2="104" stroke="#aeb9c8" stroke-width="1"/>`).join("")}<rect x="20" y="110" width="160" height="12" rx="3" fill="url(#steelDark)"/></svg>`,
    windbreak: (m) => `<svg viewBox="0 0 200 150">${frame(m)}<rect x="34" y="70" width="132" height="58" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/><rect x="40" y="24" width="120" height="40" rx="3" fill="rgba(180,205,230,.25)" stroke="#8794a6"/>${Array.from({length:5}).map((_,r)=>Array.from({length:9}).map((_,c)=>`<circle cx="${46+c*14}" cy="${80+r*10}" r="1.6" fill="#7d8b9e"/>`).join("")).join("")}</svg>`,
    stool: (m) => `<svg viewBox="0 0 200 150"><rect x="60" y="34" width="80" height="12" rx="3" fill="url(#steelGrad)" stroke="#7d8b9e"/><path d="M70 46 L52 138 M130 46 L148 138 M78 46 L96 138 M122 46 L104 138" fill="none" stroke="url(#steelDark)" stroke-width="4" stroke-linecap="round"/><line x1="66" y1="96" x2="134" y2="96" stroke="url(#steelDark)" stroke-width="3"/></svg>`,
  };
  const artFor = (icon, mobile) => (ART[icon] || ART.table)(mobile);

  /* =======================================================================
     ДАННЫЕ КАТАЛОГА
     ======================================================================= */
  const DESC = {
    sink:      "Секция с врезной мойкой и местом под смеситель. Скрытая подводка, дверцы для хранения под чашей.",
    grill:     "Секция с мангалом из стали 2 мм: усиленный каркас, зольник с выдвижным ящиком, направляющие под шампуры и решётку.",
    drawers:   "Тумба с выдвижными ящиками на шариковых направляющих. Врезные ручки, ничего не цепляется за одежду.",
    doors:     "Секция с распашными дверцами и внутренней полкой — для посуды, баллона или утвари.",
    hood:      "Купольная вытяжка из нержавейки с патрубком под дымоход и рамкой жироулавливающего фильтра.",
    table:     "Стол-остров / рабочая столешница на прочном каркасе. Нижняя полка-рейлинг для хранения.",
    shelf:     "Открытая этажерка с полками — под посуду, специи и аксессуары. Занимает мало места.",
    apron:     "Защитный фартук-экран за рабочей зоной. Беззазорный монтаж над столешницей, брызги и жир — на металле, а не на стене.",
    windbreak: "Секция с перфорированным ветрозащитным экраном и верхним стеклом — гасит ветер, не перекрывая тягу.",
    stool:     "Табурет из нержавейки в стиле кухни — устойчивая A-образная рама, оставляется на улице.",
  };
  const SERIES_BADGE = { TERRASA: "TERRASA", VERANDA: "VERANDA", "Универсал": "TERRASA / VERANDA" };
  const isMobileLook = (series) => series !== "VERANDA";
  const MODULES = (S.modules || []).map(m => ({
    ...m, desc: DESC[m.icon] || "", badge: SERIES_BADGE[m.series] || m.series, mobile: isMobileLook(m.series),
  }));
  const moduleByKey = (k) => MODULES.find(m => m.key === k);

  /* =======================================================================
     ССЫЛКИ КОНТАКТОВ
     ======================================================================= */
  const links = {
    tel: "tel:+" + (S.phoneRaw || ""),
    wa:  "https://wa.me/" + (S.whatsapp || "") + "?text=" + encodeURIComponent(`Здравствуйте! Пишу с сайта ${S.brand || ""}. Хочу узнать про уличную кухню из нержавейки.`),
    tg:  "https://t.me/" + (S.telegram || ""),
    mail:"mailto:" + (S.email || ""),
  };

  /* =======================================================================
     ШАПКА / ПОДВАЛ (вставляются на каждой странице)
     ======================================================================= */
  const NAV = [
    { href: "index.html",      label: "Главная" },
    { href: "catalog.html",    label: "Каталог" },
    { href: "calculator.html", label: "Калькулятор" },
    { href: "about.html",      label: "О производстве" },
    { href: "contacts.html",   label: "Контакты" },
  ];
  const curPage = (location.pathname.split("/").pop() || "index.html").toLowerCase() || "index.html";
  const logoSvg = (size) => `<svg class="logo-mark" viewBox="0 0 32 32" width="${size}" height="${size}" aria-hidden="true"><rect width="32" height="32" rx="7" fill="var(--accent)"/><path d="M8 21h16M8 16h16M8 11h16" stroke="#0e1116" stroke-width="2.6" stroke-linecap="round"/></svg>`;

  function buildHeader() {
    const host = $("#siteHeader"); if (!host) return;
    const navLinks = NAV.map(n => {
      const active = (n.href === curPage) || (curPage === "" && n.href === "index.html");
      return `<a href="${n.href}"${active ? ' class="active" aria-current="page"' : ""}>${n.label}</a>`;
    }).join("");
    host.className = "site-header";
    host.innerHTML = `
      <div class="container header-inner">
        <a href="index.html" class="logo" aria-label="${esc(S.brand || "TERRASA")} — на главную">
          ${logoSvg(34)}
          <span class="logo-text"><b>${esc(S.brand || "TERRASA")}</b><i>${esc(S.brandSub || "")}</i></span>
        </a>
        <nav class="main-nav" id="mainNav" aria-label="Основная навигация">
          ${navLinks}
          <a href="contacts.html" class="nav-cta">Заказать</a>
        </nav>
        <a class="header-phone" href="${links.tel}"><span>${esc(S.phonePretty || "")}</span></a>
        <button class="burger" id="burger" aria-label="Меню" aria-expanded="false"><span></span><span></span><span></span></button>
      </div>`;
  }

  function buildFooter() {
    const host = $("#siteFooter"); if (!host) return;
    host.className = "site-footer";
    host.innerHTML = `
      <div class="container footer-grid">
        <div class="footer-brand">
          <div class="logo">${logoSvg(30)}<span class="logo-text"><b>${esc(S.brand || "TERRASA")}</b></span></div>
          <p>${esc(S.brandSub || "")}</p>
          <p class="footer-legal">${esc(S.legalName || "")} · ${esc(S.city || "")}</p>
        </div>
        <nav class="footer-nav" aria-label="Разделы">
          <b>Разделы</b>
          ${NAV.map(n => `<a href="${n.href}">${n.label}</a>`).join("")}
        </nav>
        <div class="footer-contacts">
          <b>Контакты</b>
          <a href="${links.tel}">${esc(S.phonePretty || "")}</a>
          <a href="${links.wa}" target="_blank" rel="noopener">WhatsApp</a>
          <a href="${links.tg}" target="_blank" rel="noopener">Telegram</a>
          <a href="${links.mail}">${esc(S.email || "")}</a>
          <span class="footer-addr">${esc(S.address || "")}</span>
          <span class="footer-addr">${esc(S.workingHours || "")}</span>
        </div>
      </div>
      <div class="container footer-bottom">
        <span>© <span id="year"></span> ${esc(S.brand || "TERRASA")}. Все права защищены.</span>
        <a href="#top" class="to-top">Наверх ↑</a>
      </div>`;
    // Плавающая кнопка WhatsApp
    const fab = document.createElement("a");
    fab.className = "fab-whatsapp"; fab.href = links.wa;
    fab.target = "_blank"; fab.rel = "noopener";
    fab.setAttribute("aria-label", "Написать в WhatsApp");
    fab.innerHTML = `<span class="fab-ico">${ICON.whatsapp}</span>`;
    document.body.appendChild(fab);
    const y = $("#year"); if (y) y.textContent = new Date().getFullYear();
  }

  /* =======================================================================
     КАТАЛОГ (страница catalog.html и тизер на главной)
     ======================================================================= */
  function renderCatalogInto(grid, filter, limit) {
    if (!grid) return;
    let items = MODULES.filter(m => filter === "all" || filter == null ? true : (m.series === filter || m.series === "Универсал"));
    if (limit) items = items.slice(0, limit);
    grid.innerHTML = items.map(m => `
      <article class="mod-card">
        <div class="mod-figure"><span class="mod-series-badge">${m.badge}</span>${artFor(m.icon, m.mobile)}</div>
        <div class="mod-body">
          <h3>${esc(m.name)}</h3>
          <p>${esc(m.desc)}</p>
          <div class="mod-foot">
            <div class="mod-price">${fmt(m.price)}<span>цена «от»</span></div>
            <button class="mod-add" data-add="${m.key}">В расчёт +</button>
          </div>
        </div>
      </article>`).join("");
  }

  function initCatalogPage() {
    const grid = $("#catalogGrid"); if (!grid) return;
    renderCatalogInto(grid, "all");
    $$(".series-tab").forEach(tab => tab.addEventListener("click", () => {
      $$(".series-tab").forEach(t => { t.classList.remove("is-active"); t.setAttribute("aria-selected", "false"); });
      tab.classList.add("is-active"); tab.setAttribute("aria-selected", "true");
      renderCatalogInto(grid, tab.dataset.series);
      revealAll();
    }));
  }
  function initFeatured() { renderCatalogInto($("#featuredGrid"), "all", 6); }

  function initGallery() {
    const g = $("#galleryGrid"); if (!g) return;
    const pick = ["grill", "sink", "hood", "drawers", "windbreak", "table"];
    g.innerHTML = pick.map(key => {
      const m = MODULES.find(x => x.icon === key) || {};
      return `<figure class="gallery-tile">${artFor(key, isMobileLook(m.series || "Универсал"))}<figcaption class="g-cap">${esc(m.name || "")}</figcaption></figure>`;
    }).join("");
  }

  /* =======================================================================
     КОРЗИНА (общая, живёт в sessionStorage — переносится между страницами)
     ======================================================================= */
  const CART_KEY = "terrasa_cart";
  function loadCart() { try { return new Map(JSON.parse(sessionStorage.getItem(CART_KEY) || "[]")); } catch (_) { return new Map(); } }
  function saveCart() { try { sessionStorage.setItem(CART_KEY, JSON.stringify(Array.from(cart.entries()))); } catch (_) {} }
  const cart = loadCart();

  function kitText() {
    if (cart.size === 0) return "";
    let total = 0;
    const parts = Array.from(cart.entries()).map(([k, q]) => { const m = moduleByKey(k); total += m.price * q; return `${m.name} ×${q}`; });
    return parts.join(", ") + " — ориентировочно " + fmt(total);
  }

  function addToCart(key) {
    if (!moduleByKey(key)) return;
    cart.set(key, (cart.get(key) || 0) + 1);
    saveCart();
    if ($("#cartList")) renderCart(); else toast(moduleByKey(key).name);
    $$(`[data-add="${key}"]`).forEach(b => { b.style.transform = "scale(.94)"; setTimeout(() => b.style.transform = "", 130); });
  }
  function setQty(key, q) { if (q <= 0) cart.delete(key); else cart.set(key, q); saveCart(); renderCart(); }

  function renderCart() {
    const list = $("#cartList"); if (!list) return;
    let total = 0, count = 0;
    if (cart.size === 0) {
      list.innerHTML = `<li class="cart-empty">Пока пусто. Добавьте секции слева&nbsp;👈</li>`;
    } else {
      list.innerHTML = Array.from(cart.entries()).map(([key, qty]) => {
        const m = moduleByKey(key); const sum = m.price * qty; total += sum; count += qty;
        return `<li class="cart-item">
          <span class="ct-name">${esc(m.name)}<span>${fmt(m.price)} × шт.</span></span>
          <span class="qty"><button data-dec="${key}" aria-label="Меньше">−</button><span>${qty}</span><button data-inc="${key}" aria-label="Больше">+</button></span>
          <span class="ct-price">${fmt(sum)}</span>
          <button class="ct-del" data-del="${key}" aria-label="Удалить">×</button>
        </li>`;
      }).join("");
    }
    const cc = $("#cartCount"); if (cc) cc.textContent = count;
    const ct = $("#cartTotal"); if (ct) ct.innerHTML = fmt(total);
    const btn = $("#cartOrder"); if (btn) btn.disabled = cart.size === 0;
    const kf = $("#lf-kit"); if (kf) kf.value = kitText();
  }

  function initCalculator() {
    const cc = $("#configCatalog");
    if (cc) {
      cc.innerHTML = MODULES.map(m => `
        <button class="config-item" data-add="${m.key}">
          <span class="ci-fig">${artFor(m.icon, m.mobile)}</span>
          <span class="ci-meta"><span class="ci-name">${esc(m.name)}</span><span class="ci-price">от ${fmt(m.price)}</span></span>
          <span class="ci-plus">+</span>
        </button>`).join("");
    }
    if ($("#cartList")) renderCart();
    const order = $("#cartOrder");
    if (order) order.addEventListener("click", () => {
      try { sessionStorage.setItem("terrasa_kit", kitText()); } catch (_) {}
      location.href = "contacts.html#leadForm";
    });
  }

  // Клики по кнопкам «добавить / +/- / удалить» — на любой странице
  document.addEventListener("click", (e) => {
    const t = e.target;
    const add = t.closest("[data-add]"); if (add) { e.preventDefault(); addToCart(add.dataset.add); return; }
    const inc = t.closest("[data-inc]"); if (inc) { setQty(inc.dataset.inc, (cart.get(inc.dataset.inc) || 0) + 1); return; }
    const dec = t.closest("[data-dec]"); if (dec) { setQty(dec.dataset.dec, (cart.get(dec.dataset.dec) || 0) - 1); return; }
    const del = t.closest("[data-del]"); if (del) { setQty(del.dataset.del, 0); return; }
  });

  // Тост «добавлено в расчёт» (когда корзины на странице нет)
  let toastTimer = null;
  function toast(name) {
    let el = $("#toast");
    if (!el) { el = document.createElement("div"); el.id = "toast"; el.className = "toast"; document.body.appendChild(el); }
    el.innerHTML = `<b>✓ «${esc(name)}» — в расчёте.</b> <a href="calculator.html">Перейти к расчёту →</a>`;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 4000);
  }

  /* =======================================================================
     ФОРМА ЗАЯВКИ (contacts.html)
     ======================================================================= */
  function initForm() {
    const form = $("#leadForm"); if (!form) return;
    const statusEl = $("#formStatus");
    const kitField = $("#lf-kit");
    const msg = $("#lf-msg");

    // Перенос комплекта из калькулятора
    let kit = "";
    try { kit = sessionStorage.getItem("terrasa_kit") || ""; } catch (_) {}
    if (!kit) kit = kitText();
    if (kit) {
      if (kitField) kitField.value = kit;
      const hint = $("#kitHint"); if (hint) { hint.textContent = "Ваш комплект из калькулятора: " + kit; hint.style.display = "block"; }
    }

    const showError = (name, text) => {
      const err = $(`[data-error-for="${name}"]`); const input = form.querySelector(`[name="${name}"]`);
      if (err) err.textContent = text || ""; if (input) input.classList.toggle("invalid", !!text);
    };
    const validPhone = (v) => { const d = (v || "").replace(/\D/g, ""); return d.length >= 10 && d.length <= 15; };
    const setStatus = (text, kind) => { if (statusEl) { statusEl.textContent = text; statusEl.className = "form-status" + (kind ? " " + kind : ""); } };

    form.addEventListener("input", (e) => { if (e.target.name) showError(e.target.name, ""); setStatus("", ""); });

    // Проверка на blur (мягкая: только если поле заполнено, но неверно)
    const nameInp = form.querySelector('[name="name"]'), phoneInp = form.querySelector('[name="phone"]');
    if (nameInp) nameInp.addEventListener("blur", () => { const v = nameInp.value.trim(); if (v && v.length < 2) showError("name", "Укажите, как к вам обращаться"); });
    if (phoneInp) phoneInp.addEventListener("blur", () => { const v = phoneInp.value.trim(); if (v && !validPhone(v)) showError("phone", "Введите корректный телефон"); });

    form.addEventListener("submit", (e) => {
      e.preventDefault();
      if (form.company_hp && form.company_hp.value) return; // honeypot
      const d = {
        name: (form.name.value || "").trim(),
        phone: (form.phone.value || "").trim(),
        channel: form.channel.value,
        message: (form.message.value || "").trim(),
        kit: (kitField && kitField.value) || "",
      };
      let ok = true;
      if (d.name.length < 2) { showError("name", "Укажите, как к вам обращаться"); ok = false; }
      if (!validPhone(d.phone)) { showError("phone", "Введите корректный телефон"); ok = false; }
      if (!ok) { const f = form.querySelector(".invalid"); f && f.focus(); return; }

      const text = [
        `🔔 Заявка с сайта ${S.brand || ""}`, `Имя: ${d.name}`, `Телефон: ${d.phone}`,
        `Связь: ${d.channel}`, d.kit ? `Комплект: ${d.kit}` : "", d.message ? `Комментарий: ${d.message}` : "",
      ].filter(Boolean).join("\n");

      try { const box = JSON.parse(localStorage.getItem("terrasa_leads") || "[]"); box.push({ ...d, at: new Date().toISOString() }); localStorage.setItem("terrasa_leads", JSON.stringify(box)); } catch (_) {}

      const done = () => { form.reset(); cart.clear(); saveCart(); try { sessionStorage.removeItem("terrasa_kit"); } catch (_) {} };
      const mode = S.leadDelivery || "whatsapp";

      if (mode === "endpoint" && S.formEndpoint) {
        setStatus("Отправляем…", "");
        fetch(S.formEndpoint, { method: "POST", headers: { "Accept": "application/json", "Content-Type": "application/json" }, body: JSON.stringify(d) })
          .then(r => { if (r.ok) { done(); setStatus("Спасибо! Заявка отправлена — мы скоро свяжемся.", "ok"); } else throw 0; })
          .catch(() => setStatus("Не удалось отправить. Позвоните нам: " + (S.phonePretty || ""), "err"));
        return;
      }
      if (mode === "email") {
        window.location.href = `mailto:${S.email}?subject=${encodeURIComponent(`Заявка с сайта ${S.brand || ""} — ${d.name}`)}&body=${encodeURIComponent(text)}`;
        setStatus("Открываем почту… Если не открылась — напишите на " + (S.email || ""), "ok"); done(); return;
      }
      window.open("https://wa.me/" + (S.whatsapp || "") + "?text=" + encodeURIComponent(text), "_blank");
      setStatus("Открываем WhatsApp с вашей заявкой — нажмите «Отправить» в мессенджере.", "ok"); done();
    });
  }

  /* =======================================================================
     ГЕРОЙ-АРТ (главная)
     ======================================================================= */
  function initHeroArt() {
    const h = $("#heroArt"); if (!h) return;
    h.innerHTML = `<svg viewBox="0 0 520 420" role="img" aria-label="Уличная кухня из нержавеющей стали">
      <ellipse cx="260" cy="392" rx="220" ry="20" fill="rgba(0,0,0,.35)"/>
      <rect x="238" y="18" width="44" height="60" fill="url(#steelGrad)" stroke="#7d8b9e"/>
      <path d="M150 150 L214 70 H306 L370 150 Z" fill="url(#steelGrad)" stroke="#7d8b9e" stroke-width="2"/>
      <path d="M150 150 H370 V172 H150 Z" fill="url(#steelDark)" stroke="#7d8b9e"/>
      <rect x="70" y="210" width="150" height="150" rx="6" fill="url(#steelGrad)" stroke="#7d8b9e" stroke-width="2"/>
      ${[0,1,2,3].map(i=>`<rect x="84" y="${224+i*33}" width="122" height="26" rx="3" fill="none" stroke="#8794a6" stroke-width="1.6"/><rect x="128" y="${234+i*33}" width="34" height="5" rx="2.5" fill="#5a6675"/>`).join("")}
      <rect x="230" y="210" width="220" height="150" rx="6" fill="url(#steelGrad)" stroke="#7d8b9e" stroke-width="2"/>
      <rect x="250" y="196" width="180" height="26" rx="4" fill="#1a1f27" stroke="#5a6675"/>
      ${Array.from({length:8}).map((_,i)=>`<circle cx="${266+i*20}" cy="209" r="3" fill="url(#emberGrad)"/>`).join("")}
      ${Array.from({length:9}).map((_,i)=>`<line x1="${262+i*20}" y1="197" x2="${262+i*20}" y2="221" stroke="#8794a6" stroke-width="1.6"/>`).join("")}
      <path d="M300 190c-5-8 2-13-2-19 8 4 9 12 5 17M340 186c-6-10 2-16-2-23 9 5 10 14 5 20M380 190c-5-8 2-13-2-19 8 4 9 12 5 17" fill="none" stroke="url(#emberGrad)" stroke-width="4" stroke-linecap="round"/>
      <rect x="250" y="300" width="180" height="42" rx="4" fill="none" stroke="#8794a6" stroke-width="1.6"/>
      <rect x="326" y="316" width="30" height="6" rx="3" fill="#5a6675"/>
      <rect x="58" y="198" width="404" height="16" rx="4" fill="url(#steelGrad)" stroke="#7d8b9e"/>
      <rect x="78" y="360" width="14" height="18" rx="3" fill="url(#steelDark)"/>
      <rect x="196" y="360" width="14" height="18" rx="3" fill="url(#steelDark)"/>
      <rect x="430" y="360" width="14" height="18" rx="3" fill="url(#steelDark)"/>
    </svg>`;
  }

  /* =======================================================================
     ИКОНКИ / ТЕКСТЫ ИЗ CONFIG / НАВИГАЦИЯ / REVEAL
     ======================================================================= */
  function fillIcons() { $$("[data-icon]").forEach(el => { const k = el.getAttribute("data-icon"); if (ICON[k]) el.innerHTML = ICON[k]; }); }
  function fillSite() {
    $$("[data-site]").forEach(el => { const k = el.getAttribute("data-site"); if (S[k] != null) el.textContent = S[k]; });
    $$("[data-phone-link]").forEach(a => a.href = links.tel);
    $$("[data-whatsapp-link]").forEach(a => a.href = links.wa);
    $$("[data-telegram-link]").forEach(a => a.href = links.tg);
    $$("[data-email-link]").forEach(a => a.href = links.mail);
  }
  function initNav() {
    const burger = $("#burger"), nav = $("#mainNav"); if (!burger || !nav) return;
    const toggle = (open) => { nav.classList.toggle("open", open); burger.setAttribute("aria-expanded", String(open)); };
    burger.addEventListener("click", () => toggle(!nav.classList.contains("open")));
    nav.addEventListener("click", (e) => { if (e.target.tagName === "A") toggle(false); });
  }
  let io = null;
  function revealAll() {
    const els = $$(".reveal:not(.in)");
    if ("IntersectionObserver" in window) {
      if (!io) io = new IntersectionObserver((ents) => ents.forEach(en => { if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); } }), { threshold: 0.12 });
      els.forEach(el => io.observe(el));
    } else els.forEach(el => el.classList.add("in"));
  }
  function markReveals() {
    $$(".section-head, .card, .mod-card, .step, .gallery-tile, .lead-form, .config-cart, .contact-info").forEach(el => el.classList.add("reveal"));
    // Стаггер-волна для карточек внутри сеток (back.out задан в CSS)
    $$(".adv-cards, .catalog-cards, .gallery-grid, .steps").forEach(grid => {
      Array.from(grid.children).forEach((child, i) => {
        if (child.classList.contains("reveal")) child.style.transitionDelay = Math.min(i, 7) * 55 + "ms";
      });
    });
  }

  /* =======================================================================
     СТАРТ
     ======================================================================= */
  function init() {
    buildHeader(); buildFooter();
    fillIcons(); fillSite(); initNav();
    initHeroArt();
    initFeatured(); initCatalogPage(); initGallery();
    initCalculator(); initForm();
    document.title = document.title || `${S.brand || "TERRASA"} — уличные кухни из нержавеющей стали`;
    markReveals(); revealAll();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
