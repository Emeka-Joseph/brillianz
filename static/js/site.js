/* Brillianz FM — public site interactions */
(() => {
  const $ = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => [...c.querySelectorAll(s)];
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Preloader
  window.addEventListener("load", () => setTimeout(() => $(".preloader")?.classList.add("done"), 350));
  setTimeout(() => $(".preloader")?.classList.add("done"), 3500); // safety

  // Nav shadow, progress bar, back-to-top, page-hero parallax
  const nav = $(".nav"), bar = $(".progress"), toTop = $(".to-top"), heroBg = $(".page-hero .bg");
  const onScroll = () => {
    const y = scrollY, h = document.documentElement.scrollHeight - innerHeight;
    nav?.classList.toggle("scrolled", y > 20);
    if (bar) bar.style.transform = `scaleX(${h > 0 ? y / h : 0})`;
    toTop?.classList.toggle("show", y > 700);
    if (heroBg && !reduced) heroBg.style.transform = `translateY(${y * 0.3}px)`;
    processLine();
  };
  addEventListener("scroll", onScroll, { passive: true });
  toTop?.addEventListener("click", () => scrollTo({ top: 0, behavior: "smooth" }));

  // Mobile nav
  const mnav = $(".mobile-nav");
  $(".burger")?.addEventListener("click", () => mnav.classList.add("open"));
  $(".mobile-nav .close")?.addEventListener("click", () => mnav.classList.remove("open"));
  $$(".mobile-nav a").forEach(a => a.addEventListener("click", () => mnav.classList.remove("open")));

  // Reveal on scroll + counters
  const counter = el => {
    const target = +el.dataset.count, dur = 2000, t0 = performance.now();
    const tick = t => {
      const p = Math.min((t - t0) / dur, 1), e = 1 - Math.pow(1 - p, 4);
      el.textContent = Math.round(target * e).toLocaleString();
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  const io = new IntersectionObserver(entries => entries.forEach(en => {
    if (!en.isIntersecting) return;
    en.target.classList.add("in");
    if (en.target.dataset.count) counter(en.target);
    io.unobserve(en.target);
  }), { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
  $$("[data-reveal], [data-count], .step").forEach(el => io.observe(el));

  // Hero slideshow + word rotator
  const slides = $$(".hero-slides .slide"), dots = $$(".hero-dots button");
  if (slides.length) {
    let i = 0, timer;
    const show = n => {
      slides[i].classList.remove("on"); dots[i]?.classList.remove("on");
      i = (n + slides.length) % slides.length;
      slides[i].classList.add("on"); dots[i]?.classList.add("on");
      clearTimeout(timer); timer = setTimeout(() => show(i + 1), 6000);
    };
    dots.forEach((d, n) => d.addEventListener("click", () => show(n)));
    show(0);
  }
  const words = $$(".rotator > span");
  if (words.length) {
    let w = 0;
    words[0].classList.add("on");
    setInterval(() => {
      const cur = words[w]; cur.classList.remove("on"); cur.classList.add("out");
      setTimeout(() => cur.classList.remove("out"), 600);
      w = (w + 1) % words.length; words[w].classList.add("on");
    }, 2400);
  }

  // Floating soap bubbles in hero
  const cv = $("#bubbles");
  if (cv && !reduced) {
    const ctx = cv.getContext("2d");
    let W, H, bubbles = [];
    const resize = () => { W = cv.width = cv.offsetWidth * devicePixelRatio; H = cv.height = cv.offsetHeight * devicePixelRatio; };
    resize(); addEventListener("resize", resize);
    const make = (initial) => ({
      x: Math.random() * W, y: initial ? Math.random() * H : H + 40,
      r: (6 + Math.random() * 26) * devicePixelRatio, s: (.3 + Math.random() * .9) * devicePixelRatio,
      w: Math.random() * Math.PI * 2, a: .25 + Math.random() * .4,
    });
    for (let n = 0; n < 34; n++) bubbles.push(make(true));
    const draw = () => {
      ctx.clearRect(0, 0, W, H);
      bubbles.forEach((b, idx) => {
        b.y -= b.s; b.w += .02; b.x += Math.sin(b.w) * .6;
        if (b.y < -60) bubbles[idx] = make(false);
        const g = ctx.createRadialGradient(b.x - b.r * .35, b.y - b.r * .35, b.r * .1, b.x, b.y, b.r);
        g.addColorStop(0, `rgba(255,255,255,${b.a})`);
        g.addColorStop(.6, `rgba(125,211,252,${b.a * .25})`);
        g.addColorStop(1, `rgba(45,212,191,${b.a * .5})`);
        ctx.beginPath(); ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2); ctx.fillStyle = g; ctx.fill();
        ctx.lineWidth = devicePixelRatio; ctx.strokeStyle = `rgba(255,255,255,${b.a * .6})`; ctx.stroke();
      });
      requestAnimationFrame(draw);
    };
    draw();
  }

  // 3D tilt + glare on service cards
  if (!reduced && matchMedia("(hover: hover)").matches) {
    $$("[data-tilt]").forEach(card => {
      card.addEventListener("mousemove", e => {
        const r = card.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
        card.style.transform = `perspective(900px) rotateX(${(.5 - y) * 7}deg) rotateY(${(x - .5) * 7}deg) translateY(-6px)`;
        card.style.setProperty("--mx", `${x * 100}%`); card.style.setProperty("--my", `${y * 100}%`);
      });
      card.addEventListener("mouseleave", () => { card.style.transform = ""; });
    });
  }

  // Process line fill
  const pl = $(".process-line"), proc = $(".process");
  function processLine() {
    if (!pl || !proc) return;
    const r = proc.getBoundingClientRect();
    const p = Math.min(Math.max((innerHeight * .8 - r.top) / (r.height + innerHeight * .3), 0), 1);
    pl.style.setProperty("--p", p.toFixed(3));
  }

  // Before / after slider
  $$(".ba").forEach(ba => {
    let drag = false;
    const set = x => {
      const r = ba.getBoundingClientRect();
      ba.style.setProperty("--x", `${Math.min(Math.max((x - r.left) / r.width, 0), 1) * 100}%`);
    };
    ba.addEventListener("pointerdown", e => { drag = true; set(e.clientX); ba.setPointerCapture(e.pointerId); });
    ba.addEventListener("pointermove", e => drag && set(e.clientX));
    ba.addEventListener("pointerup", () => drag = false);
    // Gentle auto-demo until user interacts
    if (!reduced) {
      let t = 0, auto = true;
      ba.addEventListener("pointerdown", () => auto = false, { once: true });
      const loop = () => { if (!auto) return; t += .012; ba.style.setProperty("--x", `${50 + Math.sin(t) * 30}%`); requestAnimationFrame(loop); };
      new IntersectionObserver(([e], o) => { if (e.isIntersecting) { loop(); o.disconnect(); } }).observe(ba);
    }
  });

  // Testimonials
  const tq = $$(".testi"), td = $$(".testi-dots button");
  if (tq.length > 1) {
    let k = 0;
    const go = n => { tq[k].classList.remove("on"); td[k]?.classList.remove("on"); k = n % tq.length; tq[k].classList.add("on"); td[k]?.classList.add("on"); };
    td.forEach((d, n) => d.addEventListener("click", () => go(n)));
    setInterval(() => go(k + 1), 7000);
  }

  // Scene bubbles (service detail)
  $$(".scene[data-bubbles]").forEach(sc => {
    for (let n = 0; n < 18; n++) {
      const b = document.createElement("span"); const s = 10 + Math.random() * 40;
      b.className = "bubble";
      Object.assign(b.style, { width: s + "px", height: s + "px", left: Math.random() * 100 + "%",
        animationDuration: 5 + Math.random() * 6 + "s", animationDelay: -Math.random() * 8 + "s" });
      sc.appendChild(b);
    }
  });

  onScroll();
})();
