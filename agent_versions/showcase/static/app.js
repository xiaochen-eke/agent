const ENGINES = {
  native:    { name: "原生版 Native", badge: "tag-native",    welcome: "你好，我是原生版饥荒物品顾问（手写 if/elif + requests 直调）。问我物品配方或属性吧。" },
  langgraph: { name: "LangGraph 版",  badge: "tag-langgraph", welcome: "你好，我是 LangGraph 版饥荒物品顾问（StateGraph 节点 + 条件边）。问我物品配方或属性吧。" },
  dify:      { name: "Dify 版",       badge: "tag-dify",      welcome: "你好，我是 Dify 版饥荒物品顾问（可视化工作流，已发布）。问我物品配方或属性吧。" },
};
const ENGINE_KEYS = Object.keys(ENGINES);

let engine = null;

const homeEl = document.getElementById("home");
const chatEl = document.getElementById("chat");
const compareEl = document.getElementById("compare");
const brainEl = document.getElementById("brain");
const loginEl = document.getElementById("login");
const logEl = document.getElementById("log");
const inputEl = document.getElementById("input");
const formEl = document.getElementById("form");
const sendBtn = document.getElementById("send");
const chatNameEl = document.getElementById("chat-name");
const chatBadgeEl = document.getElementById("chat-badge");

const cmpForm = document.getElementById("cmp-form");
const cmpInput = document.getElementById("cmp-input");
const cmpSend = document.getElementById("cmp-send");
const cmpQuestion = document.getElementById("cmp-question");

const brainForm = document.getElementById("brain-form");
const brainInput = document.getElementById("brain-input");
const brainSend = document.getElementById("brain-send");
const brainStateEl = document.getElementById("brain-state");
const brainGoalEl = document.getElementById("brain-goal");
const brainLastEl = document.getElementById("brain-last");
const brainResultEl = document.getElementById("brain-result");
const brainOutEl = document.getElementById("brain-out");

// 载入 Dify 已发布应用地址
fetch("/api/config")
  .then(r => r.json())
  .then(cfg => {
    if (cfg.dify_web_url) document.getElementById("dify-link").href = cfg.dify_web_url;
  })
  .catch(() => {});

/* ---------- 微信登录 / 鉴权 ---------- */
const TOKEN_KEY = "wx_token";
let AUTH = { enabled: false, wechat: false, google: false, user: null };

function getToken() { return localStorage.getItem(TOKEN_KEY) || ""; }

// 统一请求封装：自动带 token，401 时跳登录
async function api(url, opts = {}) {
  const headers = Object.assign({}, opts.headers || {});
  const t = getToken();
  if (t) headers["Authorization"] = "Bearer " + t;
  if (opts.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
  const r = await fetch(url, Object.assign({}, opts, { headers }));
  if (r.status === 401) toLogin();
  return r;
}

async function initAuth() {
  const q = new URLSearchParams(location.search);
  if (q.has("token")) {
    localStorage.setItem(TOKEN_KEY, q.get("token"));
    history.replaceState({}, "", location.pathname); // 清掉 URL 上的 token
  }
  try {
    const r = await api("/auth/config");
    const cfg = await r.json();
    AUTH.enabled = !!cfg.enabled;
    AUTH.wechat = !!cfg.wechat;
    AUTH.google = !!cfg.google;
    AUTH.user = cfg.user || null;
    renderUser(AUTH.user);
    refreshLoginButtons();
    refreshQuota();
  } catch (e) { /* 鉴权配置读取失败不影响演示 */ }
}

function refreshLoginButtons() {
  const wx = document.getElementById("login-btn-wx");
  const gg = document.getElementById("login-btn-google");
  if (wx) wx.classList.toggle("hidden", !AUTH.wechat);
  if (gg) gg.classList.toggle("hidden", !AUTH.google);
}

function renderUser(u) {
  const bar = document.getElementById("auth-bar");
  const entry = document.getElementById("login-entry");
  if (!bar) return;
  if (!u) {
    bar.classList.add("hidden");
    if (entry) entry.classList.toggle("hidden", !AUTH.enabled);
    return;
  }
  bar.classList.remove("hidden");
  if (entry) entry.classList.add("hidden");
  const avatar = document.getElementById("auth-avatar");
  const name = document.getElementById("auth-name");
  if (avatar) { avatar.src = u.avatar || ""; avatar.style.display = u.avatar ? "" : "none"; }
  if (name) name.textContent = u.nickname || u.openid || "";
}

let qrTimer = null;

function resetLogin() {
  clearInterval(qrTimer);
  qrTimer = null;
  const box = document.getElementById("login-qr");
  const msg = document.getElementById("login-msg");
  if (box) { box.classList.add("hidden"); box.innerHTML = ""; }
  if (msg) msg.textContent = "";
}

function showLoginMsg(text) {
  const msg = document.getElementById("login-msg");
  if (msg) msg.textContent = text || "";
}

async function wxLogin() {
  resetLogin();
  showLoginMsg("正在生成二维码…");
  try {
    const r = await fetch("/auth/wechat/login");
    const data = await r.json();
    if (data.error) { showLoginMsg(data.error); return; }
    startQrLogin(data.state);
  } catch (e) {
    showLoginMsg("请求失败：" + e);
  }
}

function startQrLogin(state) {
  const box = document.getElementById("login-qr");
  const img = document.createElement("img");
  img.src = "/auth/wechat/qrcode?state=" + encodeURIComponent(state);
  img.alt = "微信扫码";
  img.onerror = () => { box.classList.add("hidden"); showLoginMsg("二维码加载失败，请重新点击登录"); };
  box.innerHTML = "";
  box.appendChild(img);
  box.classList.remove("hidden");
  showLoginMsg("请用手机微信「扫一扫」扫描上方二维码");
  const t0 = Date.now();
  clearInterval(qrTimer);
  qrTimer = setInterval(async () => {
    if (Date.now() - t0 > 5 * 60 * 1000) {
      clearInterval(qrTimer);
      showLoginMsg("二维码已过期，请重新点击登录");
      return;
    }
    try {
      const r = await fetch("/auth/status?state=" + encodeURIComponent(state));
      const d = await r.json();
      if (d.ok) {
        clearInterval(qrTimer);
        localStorage.setItem(TOKEN_KEY, d.token);
        AUTH.user = d.user;
        renderUser(d.user);
        refreshQuota();
        resetLogin();
        show(homeEl);
      } else if (d.expired) {
        clearInterval(qrTimer);
        showLoginMsg("二维码已过期，请重新点击登录");
      }
    } catch (e) { /* 轮询失败下轮再试 */ }
  }, 2000);
}

function googleLogin() { window.location.href = "/auth/google/login"; }

function openLogin() { resetLogin(); show(loginEl); }

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  AUTH.user = null;
  renderUser(null);
  refreshQuota();
  resetLogin();
  // 退出后留在当前页（游客态），不强制跳登录页
}

function toLogin() {
  // 登录可选：需要时才打开登录页，不强制
  if (AUTH.enabled) { AUTH.user = null; renderUser(null); resetLogin(); show(loginEl); }
}

initAuth();

/* ---------- 游客提问额度 + 滑块人机验证 ---------- */
let QUOTA = { limit: 3, used: 0, remaining: 3, logged_in: true };
let sliderPending = null;

async function refreshQuota() {
  try {
    const r = await api("/auth/quota");
    const d = await r.json();
    QUOTA = d;
    renderQuota();
  } catch (e) { /* 额度读取失败不影响演示 */ }
}

function renderQuota() {
  const el = document.getElementById("quota-badge");
  if (!el) return;
  if (!AUTH.enabled || QUOTA.logged_in) { el.classList.add("hidden"); return; }
  el.classList.remove("hidden");
  el.textContent = QUOTA.remaining > 0
    ? ("游客 · 还可问 " + QUOTA.remaining + " 次")
    : "游客 · 已达上限，请登录";
}

function guestBlocked() {
  return AUTH.enabled && !AUTH.user && !QUOTA.logged_in && QUOTA.remaining <= 0;
}

function promptLoginQuota() {
  if (!AUTH.enabled) return;
  openLogin();
  showLoginMsg("游客最多问 " + QUOTA.limit + " 个问题，登录后继续");
}

function requireSlider(cb) {
  if (!AUTH.enabled || AUTH.user) { cb(); return; }  // 登录用户/未启用 → 直接执行
  if (sliderPending) return;
  sliderPending = cb;
  document.getElementById("slider-modal").classList.remove("hidden");
  capInit();
}

function cancelSlider() {
  sliderPending = null;
  capStopTimer();
  CAP.running = false;
  document.getElementById("slider-modal").classList.add("hidden");
}

/* ============ 拼图滑块人机验证（Geetest 式）============
   真实照片背景（联网随机图，失败回退程序化风景）+ 底部滑轨拖拽
   随机：照片 / 凸起方向 / 尺寸 / 缺口位置 / 容差 / 配色
   状态机：loading → ready → success；倒计时 + 剩余次数 + 失败抖动 */
const CAP = {
  W: 300, H: 160, S: 44, TAB: 9, side: 0, tol: 6,
  Y: 0, gapX: 0, pieceX: 10, hx: 0,
  bg: null, ctx: null, pal: [], state: "loading",
  dragging: false, ok: false, running: false, attempts: 0, MAX: 3, TIMEOUT: 30,
  t0: 0, path: [], okT: 0, particles: [], raf: 0, timer: 0, timerId: 0, gen: 0,
  track: null, handle: null, fill: null, trackText: null, msg: null, attemptsEl: null, timerEl: null,
};

const CAP_PALETTES = [
  ["#7CFF4F", "#4FF8FF", "#FFC24F", "#B44FFF", "#FF5E7E"],
  ["#39FF14", "#0AFF7B", "#7DFFB0", "#B4FFD0", "#E6FFE6"],
  ["#FF6EC7", "#7FF3FF", "#A78BFA", "#FDE68A", "#FF9FF3"],
  ["#FFD166", "#06D6A0", "#EF476F", "#118AB2", "#F8F9FA"],
  ["#00F0FF", "#FF00C8", "#FFE600", "#00FF88", "#BFFF00"],
];

const capRand = (a, b) => a + Math.random() * (b - a);
const capInt = (a, b) => (a + Math.random() * (b - a + 1)) | 0;
const capPick = arr => arr[(Math.random() * arr.length) | 0];

function jigsawPath(ctx, x, y, s, tab, side) {
  const r = s * 0.12, cx = x + s / 2, cy = y + s / 2, t = tab;
  ctx.beginPath();
  ctx.moveTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  if (side === 0) { ctx.lineTo(cx - t, y); ctx.arc(cx, y, t, Math.PI, Math.PI * 2, false); ctx.lineTo(x + s - r, y); }
  else ctx.lineTo(x + s - r, y);
  ctx.quadraticCurveTo(x + s, y, x + s, y + r);
  if (side === 1) { ctx.lineTo(x + s, cy - t); ctx.arc(x + s, cy, t, -Math.PI / 2, Math.PI / 2, false); ctx.lineTo(x + s, y + s - r); }
  else ctx.lineTo(x + s, y + s - r);
  ctx.quadraticCurveTo(x + s, y + s, x + s - r, y + s);
  if (side === 2) { ctx.lineTo(cx + t, y + s); ctx.arc(cx, y + s, t, 0, Math.PI, false); ctx.lineTo(x + r, y + s); }
  else ctx.lineTo(x + r, y + s);
  ctx.quadraticCurveTo(x, y + s, x, y + s - r);
  if (side === 3) { ctx.lineTo(x, cy + t); ctx.arc(x, cy, t, Math.PI / 2, Math.PI * 1.5, false); ctx.lineTo(x, y + r); }
  else ctx.lineTo(x, y + r);
  ctx.closePath();
}

/* 联网加载真实照片（Lorem Picsum 随机 seed），失败/超时返回 null 走程序化回退 */
function capLoadImage() {
  return new Promise(resolve => {
    const img = new Image();
    let settled = false;
    const fail = () => { if (!settled) { settled = true; resolve(null); } };
    img.onload = () => {
      if (settled) return;
      settled = true;
      const c = document.createElement("canvas");
      c.width = CAP.W; c.height = CAP.H;
      const g = c.getContext("2d");
      const s = Math.max(CAP.W / img.width, CAP.H / img.height);
      const w = img.width * s, h = img.height * s;
      g.drawImage(img, (CAP.W - w) / 2, (CAP.H - h) / 2, w, h);  // cover 裁剪填充
      resolve(c);
    };
    img.onerror = fail;
    setTimeout(fail, 6000);
    img.src = "https://picsum.photos/seed/" + Math.floor(Math.random() * 1e9) + "/300/160";
  });
}

/* 程序化「风景照」回退：日落 / 极光 / 海洋 / 城市夜空 + 暗角颗粒 */
function capMakeScene() {
  const W = CAP.W, H = CAP.H, pal = CAP.pal;
  const c = document.createElement("canvas");
  c.width = W; c.height = H;
  const g = c.getContext("2d");
  const kind = capPick(["sunset", "aurora", "ocean", "city"]);

  if (kind === "sunset") {
    const sky = g.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#1a0b3a"); sky.addColorStop(0.5, "#7a2d5e"); sky.addColorStop(1, "#ff9a4d");
    g.fillStyle = sky; g.fillRect(0, 0, W, H);
    const sunX = capRand(W * 0.3, W * 0.7), sunY = capRand(H * 0.45, H * 0.65);
    const sg = g.createRadialGradient(sunX, sunY, 0, sunX, sunY, 60);
    sg.addColorStop(0, "rgba(255,240,180,.95)"); sg.addColorStop(1, "rgba(255,150,80,0)");
    g.fillStyle = sg; g.fillRect(sunX - 60, sunY - 60, 120, 120);
    g.fillStyle = "#1a0b2e";
    g.beginPath(); g.moveTo(0, H);
    for (let x = 0; x <= W; x += 8) g.lineTo(x, H - capRand(14, 46) * Math.sin(x * 0.03 + capRand(0, 3)));
    g.lineTo(W, H); g.closePath(); g.fill();
  } else if (kind === "aurora") {
    const sky = g.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#02040a"); sky.addColorStop(1, "#0a1c30");
    g.fillStyle = sky; g.fillRect(0, 0, W, H);
    for (let i = 0; i < 3; i++) {
      const y0 = capRand(H * 0.15, H * 0.5), col = capPick(["#39ff9e", "#4ff8ff", "#b44fff"]);
      g.save(); g.globalAlpha = capRand(0.15, 0.4);
      g.strokeStyle = col; g.lineWidth = capRand(18, 40);
      g.beginPath(); g.moveTo(0, y0);
      for (let x = 0; x <= W; x += 12) g.lineTo(x, y0 + Math.sin(x * 0.02 + i * 2) * 26 + Math.sin(x * 0.05) * 12);
      g.stroke(); g.restore();
    }
    for (let i = 0; i < 90; i++) {
      g.fillStyle = "#fff"; g.globalAlpha = capRand(0.2, 0.9);
      g.fillRect(Math.random() * W, Math.random() * H * 0.7, 1.5, 1.5);
    }
    g.globalAlpha = 1;
    g.fillStyle = "#02040a";
    g.beginPath(); g.moveTo(0, H);
    for (let x = 0; x <= W; x += 8) g.lineTo(x, H - capRand(10, 34) * Math.sin(x * 0.04));
    g.lineTo(W, H); g.closePath(); g.fill();
  } else if (kind === "ocean") {
    const sky = g.createLinearGradient(0, 0, 0, H * 0.6);
    sky.addColorStop(0, "#0b3d5c"); sky.addColorStop(1, "#6fd3e8");
    g.fillStyle = sky; g.fillRect(0, 0, W, H * 0.6);
    const sea = g.createLinearGradient(0, H * 0.6, 0, H);
    sea.addColorStop(0, "#0e6b8c"); sea.addColorStop(1, "#03222f");
    g.fillStyle = sea; g.fillRect(0, H * 0.6, W, H * 0.4);
    for (let y = H * 0.66; y < H; y += 12) {
      g.strokeStyle = "rgba(255,255,255,.12)"; g.beginPath();
      for (let x = 0; x <= W; x += 6) { const yy = y + Math.sin(x * 0.06 + y) * 3; x ? g.lineTo(x, yy) : g.moveTo(x, yy); }
      g.stroke();
    }
  } else { // city 城市夜空
    const sky = g.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, "#05060f"); sky.addColorStop(1, "#1b2a4a");
    g.fillStyle = sky; g.fillRect(0, 0, W, H);
    for (let i = 0; i < 60; i++) {
      g.fillStyle = "#fff"; g.globalAlpha = capRand(0.2, 0.8);
      g.fillRect(Math.random() * W, Math.random() * H * 0.55, 1.5, 1.5);
    }
    g.globalAlpha = 1;
    let x = 0;
    while (x < W) {
      const bw = capRand(14, 42), bh = capRand(40, 110);
      g.fillStyle = "#070a14"; g.fillRect(x, H - bh, bw, bh);
      g.fillStyle = pal[capInt(0, pal.length - 1)];
      for (let wy = H - bh + 5; wy < H - 5; wy += 9)
        for (let wx = x + 3; wx < x + bw - 3; wx += 7)
          if (Math.random() < 0.35) g.fillRect(wx, wy, 2, 3);
      x += bw + capRand(1, 6);
    }
  }

  const v = g.createRadialGradient(W / 2, H / 2, H * 0.3, W / 2, H / 2, H * 0.9);
  v.addColorStop(0, "rgba(0,0,0,0)"); v.addColorStop(1, "rgba(0,0,0,.32)");
  g.fillStyle = v; g.fillRect(0, 0, W, H);
  for (let i = 0; i < 140; i++) {
    g.fillStyle = Math.random() < 0.5 ? "rgba(255,255,255,.04)" : "rgba(0,0,0,.05)";
    g.fillRect(Math.random() * W, Math.random() * H, 1, 1);
  }
  return c;
}

function capDraw(now) {
  const { ctx, W, H, S, TAB, side, Y, gapX, pieceX, bg } = CAP;
  ctx.clearRect(0, 0, W, H);
  ctx.drawImage(bg, 0, 0);

  // 缺口（半透明 + 流动虚线）
  ctx.save();
  jigsawPath(ctx, gapX, Y, S, TAB, side);
  ctx.fillStyle = "rgba(0,0,0,.55)";
  ctx.fill();
  ctx.strokeStyle = CAP.ok ? "#33ff77" : "rgba(255,255,255,.6)";
  ctx.lineWidth = 1.5;
  ctx.setLineDash([5, 4]);
  ctx.lineDashOffset = -(now / 40);
  ctx.stroke();
  ctx.restore();

  // 拼图块（从背景同一位置裁剪 → 与缺口纹理始终一致）
  const px = CAP.ok ? gapX : pieceX;
  ctx.save();
  ctx.translate(px - gapX, 0);
  jigsawPath(ctx, gapX, Y, S, TAB, side);
  ctx.clip();
  ctx.drawImage(bg, 0, 0);
  ctx.restore();
  ctx.save();
  jigsawPath(ctx, px, Y, S, TAB, side);
  ctx.strokeStyle = CAP.ok ? "#33ff77" : "rgba(220,255,230,.95)";
  ctx.lineWidth = 2;
  ctx.shadowColor = CAP.ok ? "#33ff77" : "rgba(124,255,79,.7)";
  ctx.shadowBlur = 10;
  ctx.stroke();
  ctx.restore();

  // 角框（呼吸）
  const pulse = 0.5 + 0.5 * Math.sin(now / 300);
  ctx.save();
  ctx.strokeStyle = "rgba(124,255,79," + (0.25 + pulse * 0.4).toFixed(3) + ")";
  ctx.lineWidth = 1.5;
  const m = 6, L = 16;
  ctx.beginPath();
  ctx.moveTo(m, m + L); ctx.lineTo(m, m); ctx.lineTo(m + L, m);
  ctx.moveTo(W - m - L, m); ctx.lineTo(W - m, m); ctx.lineTo(W - m, m + L);
  ctx.moveTo(W - m, H - m - L); ctx.lineTo(W - m, H - m); ctx.lineTo(W - m - L, H - m);
  ctx.moveTo(m + L, H - m); ctx.lineTo(m, H - m); ctx.lineTo(m, H - m - L);
  ctx.stroke();
  ctx.restore();

  // CRT 纹理 + 扫描线
  ctx.save();
  ctx.globalAlpha = 0.06;
  ctx.fillStyle = "#000";
  for (let y = 0; y < H; y += 3) ctx.fillRect(0, y, W, 1);
  ctx.globalAlpha = 1;
  const sy = (now / 28) % (H + 40) - 20;
  const sg = ctx.createLinearGradient(0, sy - 8, 0, sy + 8);
  sg.addColorStop(0, "rgba(124,255,79,0)");
  sg.addColorStop(0.5, "rgba(124,255,79,.16)");
  sg.addColorStop(1, "rgba(124,255,79,0)");
  ctx.fillStyle = sg;
  ctx.fillRect(0, sy - 8, W, 16);
  ctx.restore();

  // 漂浮粒子
  ctx.save();
  for (const p of CAP.particles) {
    ctx.fillStyle = p.c;
    ctx.globalAlpha = p.a;
    ctx.fillRect(p.x, p.y, p.s, p.s);
  }
  ctx.globalAlpha = 1;
  ctx.restore();

  // 通过爆发
  if (CAP.ok) {
    const dt = now - CAP.okT;
    ctx.save();
    ctx.strokeStyle = "#33ff77";
    ctx.globalAlpha = Math.max(0, 1 - dt / 700);
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(gapX + S / 2, Y + S / 2, 12 + dt * 0.12, 0, Math.PI * 2);
    ctx.stroke();
    ctx.restore();
    ctx.font = "bold 40px monospace";
    ctx.fillStyle = "#33ff77";
    ctx.globalAlpha = Math.min(1, dt / 150);
    ctx.fillText("✓", gapX + S * 0.3, Y + S * 0.72);
    ctx.globalAlpha = 1;
  }
}

function capSetState(state, msg) {
  CAP.state = state;
  if (CAP.trackText) {
    CAP.trackText.textContent = state === "success" ? "✓ 验证通过"
      : state === "loading" ? "⏳ 加载中…" : "➜ 向右拖动滑块完成拼图";
  }
  if (msg !== undefined && CAP.msg) CAP.msg.textContent = msg;
}

function capStartTimer() {
  capStopTimer();
  CAP.timer = CAP.TIMEOUT;
  capRenderTimer();
  CAP.timerId = setInterval(() => {
    CAP.timer--;
    capRenderTimer();
    if (CAP.timer <= 0) { capStopTimer(); capSetState("ready", "超时，已自动换图"); capRefresh(); }
  }, 1000);
}
function capStopTimer() {
  if (CAP.timerId) { clearInterval(CAP.timerId); CAP.timerId = 0; }
}
function capRenderTimer() {
  if (!CAP.timerEl) return;
  CAP.timerEl.textContent = "⏱ " + CAP.timer + "s";
  CAP.timerEl.style.color = CAP.timer <= 5 ? "#FF5E7E" : "";
}
function capRenderAttempts() {
  if (!CAP.attemptsEl) return;
  const rem = Math.max(0, CAP.MAX - CAP.attempts);
  CAP.attemptsEl.textContent = "剩余 " + "▮".repeat(rem) + "▯".repeat(CAP.MAX - rem);
}
function capResetPiece() {
  CAP.pieceX = 10;
  CAP.hx = 0;
  if (CAP.handle) CAP.handle.style.left = "0px";
  if (CAP.fill) CAP.fill.style.width = "0px";
}
function capShake() {
  const box = document.querySelector(".slider-box");
  if (!box) return;
  box.classList.remove("shake");
  void box.offsetWidth;
  box.classList.add("shake");
}
function capFail(msg) {
  CAP.attempts++;
  capResetPiece();
  capRenderAttempts();
  capShake();
  if (CAP.msg) CAP.msg.textContent = msg + (CAP.attempts >= CAP.MAX ? "（已自动换图）" : "");
  if (CAP.attempts >= CAP.MAX) setTimeout(() => capRefresh(), 700);
}

async function capRandomize() {
  capStopTimer();
  const gen = ++CAP.gen;
  CAP.side = capInt(0, 3);
  CAP.S = capInt(40, 56);
  CAP.TAB = capInt(7, 13);
  CAP.tol = capInt(5, 9);
  CAP.Y = capInt(CAP.TAB + 6, CAP.H - CAP.S - 6);
  CAP.gapX = capInt(70, CAP.W - CAP.S - 70);
  CAP.ok = false;
  CAP.attempts = 0;
  CAP.pal = capPick(CAP_PALETTES);
  CAP.particles = Array.from({ length: 40 }, () => ({
    x: Math.random() * CAP.W, y: Math.random() * CAP.H,
    s: capRand(1, 2.4), c: capPick(CAP.pal),
    a: capRand(0.1, 0.6), v: capRand(0.15, 0.6),
  }));
  capResetPiece();
  capRenderAttempts();
  if (CAP.track) CAP.track.classList.remove("success");
  if (CAP.handle) { CAP.handle.classList.remove("ok"); CAP.handle.innerHTML = "<span>➜</span>"; }
  capSetState("loading", "正在加载背景…");
  CAP.bg = capMakeScene();
  capDraw(performance.now());
  const photo = await capLoadImage();
  if (gen !== CAP.gen) return;
  CAP.bg = photo || capMakeScene();
  capSetState("ready", "");
  capStartTimer();
}

function capEnsureLoop() {
  if (CAP.raf) return;
  const loop = now => {
    if (!CAP.running) { CAP.raf = 0; return; }
    for (const p of CAP.particles) {
      p.y -= p.v;
      if (p.y < -4) { p.y = CAP.H + 4; p.x = Math.random() * CAP.W; }
    }
    capDraw(now);
    CAP.raf = requestAnimationFrame(loop);
  };
  CAP.raf = requestAnimationFrame(loop);
}

function capInit() {
  const cv = document.getElementById("captcha-canvas");
  if (!cv) return;
  CAP.ctx = cv.getContext("2d");
  CAP.running = true;
  capEnsureLoop();
  capRandomize();
}

function capRefresh() {
  capRandomize();
}

function capSuccess() {
  CAP.ok = true;
  CAP.okT = performance.now();
  capStopTimer();
  CAP.handle.classList.add("ok");
  CAP.handle.innerHTML = "✓";
  if (CAP.track) CAP.track.classList.add("success");
  if (CAP.fill) CAP.fill.style.width = "100%";
  capSetState("success", "验证通过");
  const cb = sliderPending;
  sliderPending = null;
  setTimeout(() => {
    CAP.running = false;
    document.getElementById("slider-modal").classList.add("hidden");
    CAP.handle.classList.remove("ok");
    CAP.handle.innerHTML = "<span>➜</span>";
    if (CAP.track) CAP.track.classList.remove("success");
    cb && cb();
  }, 850);
}

(function initSliderDrag() {
  const cv = document.getElementById("captcha-canvas");
  const track = document.getElementById("slider-track");
  const handle = document.getElementById("slider-handle");
  const fill = document.getElementById("slider-fill");
  if (!cv || !track || !handle || !fill) return;
  CAP.track = track; CAP.handle = handle; CAP.fill = fill;
  CAP.trackText = document.getElementById("slider-track-text");
  CAP.msg = document.getElementById("slider-msg");
  CAP.attemptsEl = document.getElementById("slider-attempts");
  CAP.timerEl = document.getElementById("slider-timer");

  const applyDrag = e => {
    const r = track.getBoundingClientRect();
    const hw = handle.getBoundingClientRect().width;
    let hx = e.clientX - r.left - hw / 2;
    hx = Math.max(0, Math.min(r.width - hw, hx));
    CAP.hx = hx;
    handle.style.left = hx + "px";
    fill.style.width = (hx + hw / 2) + "px";
    CAP.pieceX = 4 + (hx / (r.width - hw)) * (CAP.W - CAP.S - 8);
    CAP.path.push(hx);
  };
  const endDrag = () => {
    if (!CAP.dragging) return;
    CAP.dragging = false;
    const dur = performance.now() - CAP.t0;
    if (dur < 120 && CAP.path.length < 4) { capFail("拖动过快，疑似异常，请重试"); return; }
    if (Math.abs(CAP.pieceX - CAP.gapX) <= CAP.tol) capSuccess();
    else capFail("未对准，请重试");
  };
  track.addEventListener("pointerdown", e => {
    if (CAP.ok || CAP.state !== "ready") return;
    CAP.dragging = true;
    CAP.t0 = performance.now();
    CAP.path = [];
    track.setPointerCapture(e.pointerId);
    applyDrag(e);
    e.preventDefault();
  });
  track.addEventListener("pointermove", e => { if (CAP.dragging) applyDrag(e); });
  track.addEventListener("pointerup", endDrag);
  track.addEventListener("pointercancel", () => { CAP.dragging = false; });
})();

function show(view) {
  [homeEl, chatEl, compareEl, brainEl, loginEl].forEach(el => el.classList.add("hidden"));
  view.classList.remove("hidden");
}

function openChat(key) {
  engine = key;
  const meta = ENGINES[key];
  chatNameEl.textContent = meta.name;
  chatBadgeEl.textContent = key === "native" ? "原生版" : key === "langgraph" ? "LangGraph 版" : "Dify 版";
  chatBadgeEl.className = "tag " + meta.badge;
  logEl.innerHTML = "";
  appendMsg("bot", meta.welcome);
  show(chatEl);
  inputEl.focus();
  loadHistory(key);
}

function openCompare() {
  resetCompare();
  show(compareEl);
  cmpInput.focus();
}

function goHome() {
  engine = null;
  show(homeEl);
}

function appendMsg(kind, text) {
  const div = document.createElement("div");
  div.className = "msg " + (kind === "user" ? "user" : kind === "err" ? "err" : "bot");
  div.textContent = kind === "user" ? "❯ " + text : text;
  logEl.appendChild(div);
  logEl.scrollTop = logEl.scrollHeight;
  return div;
}

async function loadHistory(key) {
  try {
    const r = await api("/api/history?engine=" + encodeURIComponent(key));
    const data = await r.json();
    if (engine !== key) return; // 期间已切换到别的引擎
    (data.messages || []).forEach(m => {
      if (m.role === "user") appendMsg("user", m.text);
      else if (m.role === "err") appendMsg("err", m.text);
      else appendMsg("bot", m.text);
    });
  } catch (e) {
    /* 历史读取失败不影响对话 */
  }
}

async function clearHistory() {
  if (!engine) return;
  try {
    await api("/api/history/clear", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ engine }),
    });
    const meta = ENGINES[engine];
    logEl.innerHTML = "";
    appendMsg("bot", meta.welcome);
    inputEl.focus();
  } catch (e) {
    appendMsg("err", "清空失败：" + e);
  }
}

async function send() {
  const q = inputEl.value.trim();
  if (!q || !engine || sendBtn.disabled) return;
  if (guestBlocked()) { promptLoginQuota(); return; }
  requireSlider(() => doSend(q));
}

async function doSend(q) {
  inputEl.value = "";
  appendMsg("user", q);

  const typing = appendMsg("bot", "…");
  typing.innerHTML = '<span class="typing">思考中…</span>';

  sendBtn.disabled = true;
  try {
    const r = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ engine, query: q, save: true }),
    });
    const data = await r.json();
    typing.remove();
    if (data.answer) appendMsg("bot", data.answer);
    else if (data.code === "QUOTA") { appendMsg("err", data.error || "已达上限"); promptLoginQuota(); }
    else appendMsg("err", data.error || "出错了");
  } catch (e) {
    typing.remove();
    appendMsg("err", "请求失败：" + e);
  } finally {
    sendBtn.disabled = false;
    inputEl.focus();
    refreshQuota();
  }
}

/* ---------- 并排对比 ---------- */
function resetCompare() {
  cmpQuestion.textContent = "";
  ENGINE_KEYS.forEach(e => {
    document.getElementById("time-" + e).textContent = "";
    const body = document.getElementById("body-" + e);
    body.className = "cmp-body";
    body.innerHTML = '<p class="hint">等待对比…</p>';
  });
}

function setCol(e, state, text, ms) {
  const body = document.getElementById("body-" + e);
  const timeEl = document.getElementById("time-" + e);
  timeEl.textContent = ms == null ? "" : (ms / 1000).toFixed(1) + "s";
  if (state === "loading") {
    body.className = "cmp-body loading";
    body.innerHTML = '<p class="hint">思考中…</p>';
  } else if (state === "error") {
    body.className = "cmp-body error";
    body.textContent = text;
  } else {
    body.className = "cmp-body";
    body.textContent = text;
  }
}

async function runCompare() {
  const q = cmpInput.value.trim();
  if (!q || cmpSend.disabled) return;
  if (guestBlocked()) { promptLoginQuota(); return; }
  requireSlider(() => doCompare(q));
}

async function doCompare(q) {
  cmpInput.value = "";
  cmpQuestion.textContent = "问题：" + q;
  cmpSend.disabled = true;

  // 三个引擎同时发请求，各自独立渲染
  await Promise.all(ENGINE_KEYS.map(e => {
    const t0 = Date.now();
    setCol(e, "loading");
    return askEngine(e, q, t0);
  }));

  cmpSend.disabled = false;
  cmpInput.focus();
  refreshQuota();
}

async function askEngine(e, q, t0) {
  try {
    const r = await api("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ engine: e, query: q, consume: e === "native" }),
    });
    const data = await r.json();
    const ms = Date.now() - t0;
    if (data.answer) setCol(e, "done", data.answer, ms);
    else setCol(e, "error", data.error || "出错了", ms);
  } catch (err) {
    setCol(e, "error", "请求失败：" + err, Date.now() - t0);
  }
}

formEl.addEventListener("submit", e => { e.preventDefault(); send(); });
cmpForm.addEventListener("submit", e => { e.preventDefault(); runCompare(); });

/* ---------- 游戏大脑控制台 ---------- */
function openBrain() {
  show(brainEl);
  loadBrainState();
  brainInput.focus();
}

function fmtResult(results) {
  if (!results || !results.length) return "—（游戏未回传）";
  const last = results[results.length - 1];
  const ok = last.ok ? "✅ 已执行" : "❌ 失败";
  const act = (last.verb + " " + (last.prefab || "")).trim();
  const reason = last.reason ? "：" + last.reason : "";
  return ok + " " + act + reason;
}

async function loadBrainState() {
  brainStateEl.textContent = "读取中…";
  try {
    const r = await api("/api/brain/state");
    const data = await r.json();
    if (data.error) {
      brainStateEl.innerHTML = '<span class="err">' + data.error + '</span>';
      return;
    }
    brainGoalEl.textContent = data.goal || "—";
    brainLastEl.textContent = data.last_action || "—";
    if (brainResultEl) brainResultEl.textContent = fmtResult(data.results);
    const s = data.state;
    if (!s || s.status === "empty") {
      brainStateEl.innerHTML = '<span class="muted">暂无游戏状态 —— 需要游戏 + DST mod + bridge 在跑，state_api 才会收到快照。</span>';
    } else {
      const rows = [];
      if (s.summary) rows.push(s.summary);
      else rows.push(JSON.stringify(s, null, 2));
      brainStateEl.textContent = rows.join("\n");
    }
  } catch (e) {
    brainStateEl.innerHTML = '<span class="err">读取失败：' + e + '</span>';
  }
}

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function brainRun() {
  const q = brainInput.value.trim();
  if (!q || brainSend.disabled) return;
  if (guestBlocked()) { promptLoginQuota(); return; }
  requireSlider(() => doBrainRun(q));
}

async function doBrainRun(q) {
  brainInput.value = "";
  brainOutEl.innerHTML = '<div class="out-thinking">大脑思考中…（Dify 链规划 + GLM 动作决策，约 10~30s）</div>';
  brainSend.disabled = true;
  const t0 = Date.now();
  try {
    const r = await api("/api/brain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    });
    const data = await r.json();
    const ms = Date.now() - t0;
    if (data.error) {
      if (data.code === "QUOTA") promptLoginQuota();
      brainOutEl.innerHTML = '<div class="out-error">' + esc(data.error) + '</div>';
      return;
    }
    renderBrainOut(data, ms);
    // 轮询几次，捕捉 mod 回传的执行结果（游戏+bridge 往返约需几秒）
    for (let i = 0; i < 4; i++) {
      await sleep(2500);
      loadBrainState();
    }
  } catch (e) {
    brainOutEl.innerHTML = '<div class="out-error">请求失败：' + esc(e) + '</div>';
  } finally {
    brainSend.disabled = false;
    brainInput.focus();
    refreshQuota();
  }
}

function renderBrainOut(data, ms) {
  const a = data.action;
  const actionLine = a
    ? ('动作：' + a.verb + ' ' + (a.prefab || '') + (data.pushed_action ? ' ✅ 已入队' : ' ⚠️ 入队失败'))
    : '动作：无（GLM 未找到背包/附近可执行目标，宁可不做）';
  const html =
    '<div class="out-head">指令已执行 · ' + (ms / 1000).toFixed(1) + 's</div>' +
    '<div class="out-block"><h4>💬 建议</h4><div>' + esc(data.advice || "（无）") + '</div></div>' +
    '<div class="out-block"><h4>📋 计划</h4><pre>' + esc(data.plan || "（无）") + '</pre></div>' +
    '<div class="out-block"><h4>🎮 ' + esc(actionLine) + '</h4></div>' +
    '<div class="out-block muted">回灌建议：' + (data.pushed_advice ? '✅' : '❌') +
    ' · 提示：动作真正执行需 bridge + dst_mod 在跑（state_api 队列只是暂存）。</div>';
  brainOutEl.innerHTML = html;
  loadBrainState();
}

brainForm.addEventListener("submit", e => { e.preventDefault(); brainRun(); });

/* ---------- 主题 / 字号 / 主题色 ---------- */
const ROOT = document.documentElement;
const LS = { theme: "ac_theme", accent: "ac_accent", fs: "ac_fs" };

function curTheme() { return localStorage.getItem(LS.theme) || "dark"; }
function curAccent() { return localStorage.getItem(LS.accent) || "amber"; }
function curFs() { return parseFloat(localStorage.getItem(LS.fs)) || 16; }

function refreshCtl() {
  const t = curTheme();
  document.getElementById("theme-toggle").textContent = t === "dark" ? "🌙" : "☀";
  document.getElementById("fs-val").textContent = curFs() + "px";
  document.querySelectorAll("#accents .dot").forEach(d => {
    d.classList.toggle("active", d.dataset.accent === curAccent());
  });
}

document.getElementById("theme-toggle").addEventListener("click", () => {
  const next = curTheme() === "dark" ? "light" : "dark";
  localStorage.setItem(LS.theme, next);
  ROOT.setAttribute("data-theme", next);
  refreshCtl();
});

document.getElementById("fs-down").addEventListener("click", () => setFs(curFs() - 1));
document.getElementById("fs-up").addEventListener("click", () => setFs(curFs() + 1));

function setFs(fs) {
  fs = Math.min(22, Math.max(13, fs));
  localStorage.setItem(LS.fs, fs);
  ROOT.style.setProperty("--fs", fs + "px");
  refreshCtl();
}

document.querySelectorAll("#accents .dot").forEach(d => {
  d.addEventListener("click", () => {
    localStorage.setItem(LS.accent, d.dataset.accent);
    ROOT.setAttribute("data-accent", d.dataset.accent);
    refreshCtl();
  });
});

refreshCtl();

/* ---------- 封面启动动画 ---------- */
const landingEl = document.getElementById("landing");
const bootLogEl = document.getElementById("boot-log");
const enterBtn = document.getElementById("enter-btn");
let entered = false;
let skipTyping = false;

const BOOT_LINES = [
  "$ ./agent_versions --showcase",
  "> 原生手写 if/elif · LangGraph 建图 · Dify 可视化",
  "> 三引擎并排对比 · 游戏大脑控制台",
  "> [ OK ] 系统就绪，等待接入…",
];

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function runBoot() {
  bootLogEl.textContent = "";
  for (const line of BOOT_LINES) {
    for (let i = 0; i < line.length; i++) {
      if (skipTyping) return;
      bootLogEl.textContent += line[i];
      await sleep(13);
    }
    if (skipTyping) return;
    bootLogEl.textContent += "\n";
    await sleep(130);
  }
  if (!skipTyping) finishBoot();
}

function finishBoot() {
  skipTyping = true;
  enterBtn.classList.add("ready");
  enterBtn.disabled = false;
}

function enterApp() {
  if (entered) return;
  entered = true;
  [_emberIv, _leafIv, _clockIv, _camIv].forEach(iv => iv && clearInterval(iv));
  landingEl.classList.add("landing-out");
  setTimeout(() => {
    landingEl.classList.add("hidden");
    landingEl.classList.remove("landing-out");
    show(homeEl);
  }, 450);
}

enterBtn.addEventListener("click", enterApp);

landingEl.addEventListener("click", () => {
  if (!enterBtn.classList.contains("ready")) {
    skipTyping = true;
    bootLogEl.textContent = BOOT_LINES.join("\n") + "\n";
    finishBoot();
  }
});

document.addEventListener("keydown", e => {
  if (e.key === "Enter" && !landingEl.classList.contains("hidden")) {
    if (!enterBtn.classList.contains("ready")) {
      skipTyping = true;
      bootLogEl.textContent = BOOT_LINES.join("\n") + "\n";
      finishBoot();
    } else {
      enterApp();
    }
  }
});

runBoot();

/* ---------- 饥荒场景：火星 + 落叶 + 监控时钟 ---------- */
const dsEmbers = document.getElementById("ds-embers");
const dsLeaves = document.getElementById("ds-leaves");
const camTime = document.getElementById("cam-time");
let _emberIv = null, _leafIv = null, _clockIv = null, _camIv = null;

if (dsEmbers) {
  _emberIv = setInterval(() => {
    if (document.hidden) return;
    const s = document.createElement("span");
    s.className = "ember";
    const sz = (4 + Math.random() * 5).toFixed(1);
    s.style.width = sz + "px";
    s.style.height = sz + "px";
    s.style.left = (Math.random() * 22 - 11) + "px";
    s.style.animationDuration = (1.4 + Math.random() * 1.9).toFixed(2) + "s";
    dsEmbers.appendChild(s);
    setTimeout(() => s.remove(), 3400);
  }, 200);
}

if (dsLeaves) {
  _leafIv = setInterval(() => {
    if (document.hidden) return;
    const l = document.createElement("span");
    l.className = "leaf";
    l.style.left = (Math.random() * 100) + "%";
    l.style.animationDuration = (7 + Math.random() * 7).toFixed(2) + "s";
    l.style.transform = "scale(" + (0.6 + Math.random()).toFixed(2) + ")";
    dsLeaves.appendChild(l);
    setTimeout(() => l.remove(), 15000);
  }, 700);
}

function tickClock() {
  if (!camTime) return;
  const n = new Date();
  const p = x => String(x).padStart(2, "0");
  camTime.textContent = "DAY 1 · " + p(n.getHours()) + ":" + p(n.getMinutes()) + ":" + p(n.getSeconds());
}
if (camTime) {
  tickClock();
  _clockIv = setInterval(tickClock, 1000);
}

/* ---------- 角色原画轮播 ---------- */
const camShot = document.getElementById("cam-shot");
const camLabel = document.getElementById("cam-label");
const CAM_SLIDES = [
  { src: "/static/game/char_dst_hero.jpg",    label: "饥荒联机版 · 角色阵容" },
  { src: "/static/game/char_ds_hero.jpg",     label: "饥荒 · 生存荒野" },
  { src: "/static/game/char_dst_capsule.jpg", label: "饥荒联机版 · 封面" },
  { src: "/static/game/char_ds_header.jpg",   label: "饥荒 · 宣传主图" },
  { src: "/static/game/char_dst_header.jpg",  label: "饥荒联机版 · 主视觉" },
];
let camIdx = 0;

if (camShot) {
  CAM_SLIDES.forEach((s, i) => {
    const img = document.createElement("img");
    img.className = "cam-img" + (i === 0 ? " active" : "");
    img.src = s.src;
    img.alt = s.label;
    img.draggable = false;
    camShot.appendChild(img);
  });
  if (camLabel) camLabel.textContent = CAM_SLIDES[0].label;
  _camIv = setInterval(() => {
    const imgs = camShot.querySelectorAll(".cam-img");
    if (!imgs.length) return;
    imgs[camIdx].classList.remove("active");
    camIdx = (camIdx + 1) % imgs.length;
    imgs[camIdx].classList.add("active");
    if (camLabel) camLabel.textContent = CAM_SLIDES[camIdx].label;
  }, 5000);
}

/* ---------- 场景 / 视频背景切换（顶部分段切换器） ---------- */
const dsVideoEl = document.getElementById("ds-video");
const sceneTabs = document.querySelectorAll(".scene-tab");
const soundToggle = document.getElementById("sound-toggle");

function setVideoMode(on) {
  landingEl.classList.toggle("video-mode", on);
  sceneTabs.forEach(t => t.classList.toggle("active", t.dataset.mode === (on ? "video" : "scene")));
  if (soundToggle) soundToggle.classList.toggle("hidden", !on);
  if (dsVideoEl) {
    if (on) dsVideoEl.play().catch(() => {});
    else dsVideoEl.pause();
  }
}

sceneTabs.forEach(t => {
  t.addEventListener("click", () => setVideoMode(t.dataset.mode === "video"));
});
if (soundToggle) {
  soundToggle.addEventListener("click", () => {
    if (!dsVideoEl) return;
    dsVideoEl.muted = !dsVideoEl.muted;
    soundToggle.textContent = dsVideoEl.muted ? "🔊 开声音" : "🔇 静音";
  });
}

// 初始为篝火场景：暂停视频（虽 opacity 隐藏，避免后台空转）
if (dsVideoEl) dsVideoEl.pause();
