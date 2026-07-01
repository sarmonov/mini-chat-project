/* ================= Mini Telegram — frontend logikasi ================= */

const API = "";  // bir xil origin
const $ = (id) => document.getElementById(id);

const state = {
  token: localStorage.getItem("token") || null,
  me: null,
  chats: [],                 // ChatOut[]
  activeChatId: null,
  messages: {},              // chatId -> MessageOut[]
  ws: null,
  presence: {},              // userId -> bool (online)
  typing: {},                // chatId -> { userId: {name, timer} }
  attachment: null,          // {media_url, media_type, media_name}
  authMode: "login",
  searchTimer: null,
  typingSentAt: 0,
  loadingOlder: false,
};

/* ---------------- Yordamchilar ---------------- */
const esc = (s) => (s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function initials(name) {
  const parts = (name || "?").trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts[1]?.[0] || "")).toUpperCase() || "?";
}
function fmtTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}
function fmtDay(iso) {
  const d = new Date(iso), now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  const yst = new Date(now); yst.setDate(now.getDate() - 1);
  if (sameDay) return "Bugun";
  if (d.toDateString() === yst.toDateString()) return "Kecha";
  return d.toLocaleDateString([], { day: "numeric", month: "long" });
}
function fmtLastSeen(iso) {
  if (!iso) return "oxirgi tashrif noma'lum";
  const d = new Date(iso), diff = (Date.now() - d) / 1000;
  if (diff < 60) return "hozirgina onlayn edi";
  if (diff < 3600) return `${Math.floor(diff / 60)} daqiqa oldin`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} soat oldin`;
  return d.toLocaleDateString([], { day: "numeric", month: "short" });
}
function avatarHtml(name, url, cls = "avatar") {
  if (url) return `<div class="${cls}" style="background-image:url('${esc(url)}')"></div>`;
  return `<div class="${cls}">${esc(initials(name))}</div>`;
}

/* ---------------- API ---------------- */
async function api(path, { method = "GET", body, form } = {}) {
  const headers = {};
  if (state.token) headers["Authorization"] = "Bearer " + state.token;
  let payload;
  if (form) { payload = form; }
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }

  const res = await fetch(API + path, { method, headers, body: payload });
  if (res.status === 401) { doLogout(); throw new Error("Avtorizatsiya kerak"); }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) throw new Error(data?.detail || "So'rovda xatolik");
  return data;
}

/* ================= AUTH ================= */
function setAuthMode(mode) {
  state.authMode = mode;
  const reg = mode === "register";
  $("auth-title").textContent = reg ? "Ro'yxatdan o'tish" : "Mini Telegram";
  $("auth-subtitle").textContent = reg ? "Yangi hisob yarating" : "Hisobingizga kiring";
  $("auth-submit").textContent = reg ? "Ro'yxatdan o'tish" : "Kirish";
  $("name-field").style.display = reg ? "block" : "none";
  $("switch-text").textContent = reg ? "Hisobingiz bormi?" : "Hisobingiz yo'qmi?";
  $("switch-link").textContent = reg ? "Kirish" : "Ro'yxatdan o'tish";
  $("auth-error").textContent = "";
}

$("switch-link").onclick = (e) => { e.preventDefault(); setAuthMode(state.authMode === "login" ? "register" : "login"); };

$("auth-form").onsubmit = async (e) => {
  e.preventDefault();
  $("auth-error").textContent = "";
  const username = $("username").value.trim();
  const password = $("password").value;
  const display_name = $("display_name").value.trim();
  try {
    const path = state.authMode === "register" ? "/api/auth/register" : "/api/auth/login";
    const body = state.authMode === "register"
      ? { username, password, display_name: display_name || username }
      : { username, password };
    const data = await api(path, { method: "POST", body });
    state.token = data.access_token;
    localStorage.setItem("token", state.token);
    state.me = data.user;
    await boot();
  } catch (err) {
    $("auth-error").textContent = err.message;
  }
};

function doLogout() {
  localStorage.removeItem("token");
  state.token = null; state.me = null; state.chats = []; state.activeChatId = null;
  if (state.ws) { try { state.ws.close(); } catch {} state.ws = null; }
  $("app").classList.add("hidden");
  $("auth-screen").classList.remove("hidden");
}
$("logout-btn").onclick = doLogout;

/* ================= BOOT ================= */
async function boot() {
  if (!state.me) state.me = await api("/api/users/me");
  $("auth-screen").classList.add("hidden");
  $("app").classList.remove("hidden");

  $("me-name").textContent = state.me.display_name;
  $("me-username").textContent = "@" + state.me.username;
  $("me-avatar").outerHTML = avatarHtml(state.me.display_name, state.me.avatar_url).replace('class="avatar"', 'class="avatar" id="me-avatar"');

  await loadChats();
  connectWS();
}

async function loadChats() {
  state.chats = await api("/api/chats");
  renderChatList();
}

/* ================= CHAT LIST ================= */
function chatDisplay(chat) {
  // title/avatar build_chat_out'da to'g'rilangan; private uchun other user id topamiz
  let otherId = null;
  if (chat.type === "private") {
    const om = chat.members.find((m) => m.user.id !== state.me.id);
    otherId = om?.user.id ?? null;
  }
  return { title: chat.title || "Suhbat", avatar: chat.avatar_url, otherId };
}

function renderChatList() {
  const el = $("chat-list");
  if (!state.chats.length) {
    el.innerHTML = `<div style="padding:24px;text-align:center;color:var(--text-dim);font-size:14px">Hali suhbat yo'q.<br>✎ tugmasi orqali boshlang.</div>`;
    return;
  }
  el.innerHTML = state.chats.map((chat) => {
    const d = chatDisplay(chat);
    const online = d.otherId && state.presence[d.otherId];
    const last = chat.last_message;
    let preview = "Suhbat boshlandi";
    if (last) {
      const who = last.sender_id === state.me.id ? "Siz: " : "";
      preview = who + (last.media_type === "image" ? "🖼 Rasm" : last.media_type === "file" ? "📎 " + (last.media_name || "Fayl") : esc(last.content));
    }
    return `
      <div class="chat-item ${chat.id === state.activeChatId ? "active" : ""}" data-id="${chat.id}">
        <div class="avatar">${d.avatar ? "" : esc(initials(d.title))}
          ${d.avatar ? `<div style="position:absolute;inset:0;border-radius:50%;background-image:url('${esc(d.avatar)}');background-size:cover"></div>` : ""}
          ${online ? '<span class="online-dot"></span>' : ""}
        </div>
        <div class="chat-body">
          <div class="chat-row">
            <span class="chat-name">${chat.type === "group" ? "👥 " : ""}${esc(d.title)}</span>
            <span class="chat-time">${last ? fmtTime(last.created_at) : ""}</span>
          </div>
          <div class="chat-row">
            <span class="chat-preview">${preview}</span>
            ${chat.unread_count ? `<span class="badge">${chat.unread_count}</span>` : ""}
          </div>
        </div>
      </div>`;
  }).join("");

  el.querySelectorAll(".chat-item").forEach((n) =>
    n.onclick = () => openChat(Number(n.dataset.id)));
}

/* ================= CONVERSATION ================= */
async function openChat(chatId) {
  state.activeChatId = chatId;
  const chat = state.chats.find((c) => c.id === chatId);
  if (!chat) return;
  chat.unread_count = 0;
  renderChatList();

  $("empty-state").classList.add("hidden");
  $("conversation").classList.remove("hidden");
  $("app").classList.add("chat-open");

  const d = chatDisplay(chat);
  $("conv-avatar").outerHTML = avatarHtml(d.title, d.avatar, "conv-avatar").replace('class="conv-avatar"', 'class="conv-avatar" id="conv-avatar"');
  $("conv-title").textContent = (chat.type === "group" ? "👥 " : "") + d.title;
  updateConvStatus(chat);

  // xabarlarni yuklaymiz
  if (!state.messages[chatId]) {
    const msgs = await api(`/api/chats/${chatId}/messages`);
    state.messages[chatId] = msgs;
  }
  renderMessages(chatId);
  markReadLatest(chatId);
}

function updateConvStatus(chat) {
  const st = $("conv-status");
  const d = chatDisplay(chat);
  if (chat.type === "group") {
    st.className = "conv-status";
    st.textContent = `${chat.members.length} a'zo`;
  } else {
    const online = d.otherId && state.presence[d.otherId];
    const other = chat.members.find((m) => m.user.id === d.otherId)?.user;
    st.className = "conv-status" + (online ? " online" : "");
    st.textContent = online ? "onlayn" : fmtLastSeen(other?.last_seen);
  }
}

function renderMessages(chatId) {
  const box = $("messages");
  const msgs = state.messages[chatId] || [];
  const chat = state.chats.find((c) => c.id === chatId);
  let html = "", lastDay = "", lastSender = null;

  msgs.forEach((m) => {
    const day = fmtDay(m.created_at);
    if (day !== lastDay) { html += `<div class="day-divider">${day}</div>`; lastDay = day; lastSender = null; }
    html += renderBubble(m, chat, lastSender === m.sender_id);
    lastSender = m.sender_id;
  });
  box.innerHTML = html;
  box.querySelectorAll(".media-img").forEach((img) => img.onclick = () => window.open(img.src, "_blank"));
  box.scrollTop = box.scrollHeight;
}

function renderBubble(m, chat, grouped) {
  const out = m.sender_id === state.me.id;
  const showSender = chat?.type === "group" && !out;
  let inner = "";
  if (m.media_type === "image") inner += `<img class="media-img" src="${esc(m.media_url)}" alt="rasm">`;
  else if (m.media_type === "file") inner += `<div class="file-att"><span class="file-ico">📎</span><a href="${esc(m.media_url)}" target="_blank" download>${esc(m.media_name || "Fayl")}</a></div>`;
  if (m.content) inner += esc(m.content);

  let ticks = "";
  if (out) {
    const read = isReadByOthers(chat, m.id);
    ticks = `<span class="ticks ${read ? "read" : ""}">${read ? "✓✓" : (m._pending ? "🕓" : "✓")}</span>`;
  }
  const senderName = showSender ? `<div class="msg-sender">${esc(m.sender_name || "")}</div>` : "";
  return `
    <div class="msg-row ${out ? "out" : "in"} ${grouped ? "msg-grouped" : ""}" data-mid="${m.id}">
      ${senderName}
      <div class="bubble">${inner}
        <div class="msg-meta"><span>${fmtTime(m.created_at)}</span>${ticks}</div>
      </div>
    </div>`;
}

function isReadByOthers(chat, msgId) {
  if (!chat) return false;
  return chat.members.some((m) =>
    m.user.id !== state.me.id && (m.last_read_message_id || 0) >= msgId);
}

/* ---------- Xabar qo'shish (yangi kelgan) ---------- */
function appendMessage(m) {
  const chatId = m.chat_id;
  if (!state.messages[chatId]) state.messages[chatId] = [];
  const list = state.messages[chatId];

  // optimistik xabarni almashtiramiz (client_id bo'yicha)
  if (m.client_id) {
    const idx = list.findIndex((x) => x._client_id === m.client_id);
    if (idx !== -1) { list[idx] = m; if (chatId === state.activeChatId) renderMessages(chatId); return; }
  }
  if (list.some((x) => x.id === m.id)) return;  // dublikat
  list.push(m);

  const chat = state.chats.find((c) => c.id === chatId);
  if (chat) chat.last_message = m;

  if (chatId === state.activeChatId) {
    renderMessages(chatId);
    if (m.sender_id !== state.me.id) markReadLatest(chatId);
  } else if (chat && m.sender_id !== state.me.id) {
    chat.unread_count = (chat.unread_count || 0) + 1;
  }
  // ro'yxatni yangilash (oxirgi xabar/tartib)
  state.chats.sort((a, b) => {
    const ta = a.last_message ? new Date(a.last_message.created_at) : 0;
    const tb = b.last_message ? new Date(b.last_message.created_at) : 0;
    return tb - ta;
  });
  renderChatList();
}

/* ================= YUBORISH ================= */
function autoGrow() { const t = $("msg-input"); t.style.height = "auto"; t.style.height = Math.min(t.scrollHeight, 140) + "px"; }
$("msg-input").addEventListener("input", () => { autoGrow(); sendTyping(); });
$("msg-input").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
});
$("send-btn").onclick = sendMessage;

function sendMessage() {
  const input = $("msg-input");
  const content = input.value.trim();
  if (!content && !state.attachment) return;
  if (!state.activeChatId || !state.ws || state.ws.readyState !== WebSocket.OPEN) return;

  const clientId = "c" + Date.now() + Math.random().toString(36).slice(2, 6);
  const att = state.attachment || {};
  // optimistik ko'rsatish
  const optimistic = {
    id: -Date.now(), _client_id: clientId, _pending: true,
    chat_id: state.activeChatId, sender_id: state.me.id, sender_name: state.me.display_name,
    content, media_url: att.media_url, media_type: att.media_type, media_name: att.media_name,
    created_at: new Date().toISOString(),
  };
  (state.messages[state.activeChatId] ||= []).push(optimistic);
  renderMessages(state.activeChatId);

  state.ws.send(JSON.stringify({
    type: "message", chat_id: state.activeChatId, content,
    media_url: att.media_url, media_type: att.media_type, media_name: att.media_name,
    client_id: clientId,
  }));

  input.value = ""; autoGrow(); clearAttachment();
}

function sendTyping() {
  const now = Date.now();
  if (now - state.typingSentAt < 2500) return;
  state.typingSentAt = now;
  if (state.ws?.readyState === WebSocket.OPEN && state.activeChatId)
    state.ws.send(JSON.stringify({ type: "typing", chat_id: state.activeChatId }));
}

function markReadLatest(chatId) {
  const list = state.messages[chatId] || [];
  const last = [...list].reverse().find((m) => m.id > 0 && m.sender_id !== state.me.id);
  if (last && state.ws?.readyState === WebSocket.OPEN)
    state.ws.send(JSON.stringify({ type: "read", chat_id: chatId, message_id: last.id }));
}

/* ================= FILE UPLOAD ================= */
$("file-input").onchange = async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData(); fd.append("file", file);
  $("attach-preview").classList.remove("hidden");
  $("attach-preview").innerHTML = "⏳ yuklanmoqda...";
  try {
    const res = await api("/api/upload", { method: "POST", form: fd });
    state.attachment = res;
    const thumb = res.media_type === "image" ? `<img src="${esc(res.media_url)}">` : "📎";
    $("attach-preview").innerHTML = `${thumb}<span>${esc(res.media_name)}</span><span class="rm" id="rm-att">✕</span>`;
    $("rm-att").onclick = clearAttachment;
  } catch (err) { $("attach-preview").innerHTML = "❌ " + err.message; }
  e.target.value = "";
};
function clearAttachment() {
  state.attachment = null;
  $("attach-preview").classList.add("hidden");
  $("attach-preview").innerHTML = "";
}

/* ================= WEBSOCKET ================= */
function connectWS() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(state.token)}`);
  state.ws = ws;

  ws.onopen = () => { state._hb = setInterval(() => ws.readyState === 1 && ws.send(JSON.stringify({ type: "heartbeat" })), 15000); };
  ws.onclose = () => { clearInterval(state._hb); if (state.token) setTimeout(connectWS, 2000); };
  ws.onmessage = (ev) => {
    let data; try { data = JSON.parse(ev.data); } catch { return; }
    dispatchEvent(data);
  };
}

function dispatchEvent(d) {
  switch (d.type) {
    case "message": appendMessage(d); break;
    case "typing": handleTyping(d); break;
    case "read": handleRead(d); break;
    case "presence": handlePresence(d); break;
    case "chat_update": loadChats(); break;
    case "error": console.warn("WS xato:", d.message); break;
  }
}

function handleTyping(d) {
  const chatId = d.chat_id;
  state.typing[chatId] ||= {};
  clearTimeout(state.typing[chatId][d.user_id]?.timer);
  state.typing[chatId][d.user_id] = {
    name: d.user_name,
    timer: setTimeout(() => { delete state.typing[chatId][d.user_id]; renderTyping(); }, 4000),
  };
  renderTyping();
}
function renderTyping() {
  const bar = $("typing-bar");
  const t = state.typing[state.activeChatId] || {};
  const names = Object.values(t).map((x) => x.name);
  bar.textContent = names.length ? (names.length === 1 ? `${names[0]} yozmoqda...` : `${names.join(", ")} yozishmoqda...`) : "";
}

function handleRead(d) {
  const chat = state.chats.find((c) => c.id === d.chat_id);
  if (!chat) return;
  const m = chat.members.find((x) => x.user.id === d.user_id);
  if (m) m.last_read_message_id = Math.max(m.last_read_message_id || 0, d.message_id);
  if (d.chat_id === state.activeChatId) renderMessages(d.chat_id);
}

function handlePresence(d) {
  state.presence[d.user_id] = d.online;
  // last_seen yangilash
  state.chats.forEach((c) => {
    const m = c.members.find((x) => x.user.id === d.user_id);
    if (m && d.last_seen) m.user.last_seen = d.last_seen;
  });
  renderChatList();
  const active = state.chats.find((c) => c.id === state.activeChatId);
  if (active && active.members.some((m) => m.user.id === d.user_id)) updateConvStatus(active);
}

/* ================= QIDIRUV (foydalanuvchi) ================= */
$("search-input").addEventListener("input", (e) => {
  const q = e.target.value.trim();
  clearTimeout(state.searchTimer);
  if (!q) { $("search-results").classList.add("hidden"); $("chat-list").classList.remove("hidden"); return; }
  state.searchTimer = setTimeout(() => doSearch(q), 300);
});
async function doSearch(q) {
  try {
    const users = await api(`/api/users/search?q=${encodeURIComponent(q)}`);
    const el = $("search-results");
    el.classList.remove("hidden");
    $("chat-list").classList.add("hidden");
    el.innerHTML = users.length
      ? users.map((u) => `<div class="chat-item" data-uid="${u.id}">${avatarHtml(u.display_name, u.avatar_url)}<div class="chat-body"><div class="chat-name">${esc(u.display_name)}</div><div class="chat-preview">@${esc(u.username)}</div></div></div>`).join("")
      : `<div style="padding:24px;text-align:center;color:var(--text-dim)">Hech kim topilmadi</div>`;
    el.querySelectorAll("[data-uid]").forEach((n) => n.onclick = () => startPrivate(Number(n.dataset.uid)));
  } catch (err) { console.warn(err); }
}
async function startPrivate(userId) {
  const chat = await api("/api/chats/private", { method: "POST", body: { user_id: userId } });
  $("search-input").value = ""; $("search-results").classList.add("hidden"); $("chat-list").classList.remove("hidden");
  if (!state.chats.some((c) => c.id === chat.id)) state.chats.unshift(chat);
  renderChatList(); openChat(chat.id);
}

/* ================= YANGI SUHBAT / GURUH tugmalari ================= */
$("new-chat-btn").onclick = () => { $("search-input").focus(); };
$("new-group-btn").onclick = openGroupModal;
$("back-btn").onclick = () => { state.activeChatId = null; $("app").classList.remove("chat-open"); $("conversation").classList.add("hidden"); $("empty-state").classList.remove("hidden"); renderChatList(); };
$("chat-info-btn").onclick = openChatInfo;

/* ---------- Modal yordamchi ---------- */
function showModal(html) { $("modal").innerHTML = html; $("modal-overlay").classList.remove("hidden"); }
function closeModal() { $("modal-overlay").classList.add("hidden"); $("modal").innerHTML = ""; }
$("modal-overlay").onclick = (e) => { if (e.target === $("modal-overlay")) closeModal(); };

/* ---------- Yangi guruh ---------- */
function openGroupModal() {
  const selected = new Map();
  showModal(`
    <div class="modal-head"><span>Yangi guruh</span><button class="icon-btn" id="m-close">✕</button></div>
    <div class="modal-body">
      <input class="text" id="g-title" placeholder="Guruh nomi" maxlength="128">
      <input class="text" id="g-search" placeholder="A'zo qidirish...">
      <div id="g-results"></div>
      <div id="g-selected" style="margin-top:8px;font-size:13px;color:var(--text-dim)"></div>
    </div>
    <div class="modal-foot">
      <button class="btn-ghost" id="g-cancel">Bekor</button>
      <button class="btn-accent" id="g-create" disabled>Yaratish</button>
    </div>`);
  $("m-close").onclick = closeModal; $("g-cancel").onclick = closeModal;

  const refresh = () => {
    $("g-selected").textContent = selected.size ? "Tanlangan: " + [...selected.values()].map((u) => u.display_name).join(", ") : "";
    $("g-create").disabled = !($("g-title").value.trim() && selected.size);
  };
  $("g-title").oninput = refresh;
  let t;
  $("g-search").oninput = (e) => {
    clearTimeout(t); const q = e.target.value.trim();
    if (!q) { $("g-results").innerHTML = ""; return; }
    t = setTimeout(async () => {
      const users = await api(`/api/users/search?q=${encodeURIComponent(q)}`);
      $("g-results").innerHTML = users.map((u) => `
        <div class="user-row" data-uid="${u.id}">${avatarHtml(u.display_name, u.avatar_url, "avatar sm")}
          <div><div class="u-name">${esc(u.display_name)}</div><div class="u-username">@${esc(u.username)}</div></div>
          <span class="u-check">${selected.has(u.id) ? "✓" : ""}</span></div>`).join("");
      $("g-results").querySelectorAll("[data-uid]").forEach((n) => n.onclick = () => {
        const id = Number(n.dataset.uid);
        const u = users.find((x) => x.id === id);
        if (selected.has(id)) selected.delete(id); else selected.set(id, u);
        n.querySelector(".u-check").textContent = selected.has(id) ? "✓" : "";
        refresh();
      });
    }, 300);
  };
  $("g-create").onclick = async () => {
    const chat = await api("/api/chats/group", { method: "POST", body: { title: $("g-title").value.trim(), member_ids: [...selected.keys()] } });
    closeModal();
    if (!state.chats.some((c) => c.id === chat.id)) state.chats.unshift(chat);
    renderChatList(); openChat(chat.id);
  };
}

/* ---------- Chat info ---------- */
function openChatInfo() {
  const chat = state.chats.find((c) => c.id === state.activeChatId);
  if (!chat) return;
  const d = chatDisplay(chat);
  const membersHtml = chat.members.map((m) => `
    <div class="user-row">${avatarHtml(m.user.display_name, m.user.avatar_url, "avatar sm")}
      <div><div class="u-name">${esc(m.user.display_name)} ${m.user.id === state.me.id ? "(siz)" : ""}</div>
      <div class="u-username">@${esc(m.user.username)} · ${m.role}</div></div>
      ${state.presence[m.user.id] ? '<span class="u-check" style="color:var(--online)">●</span>' : ""}</div>`).join("");

  const isGroup = chat.type === "group";
  showModal(`
    <div class="modal-head"><span>${isGroup ? "Guruh" : "Profil"}</span><button class="icon-btn" id="m-close">✕</button></div>
    <div class="modal-body" style="text-align:center">
      ${avatarHtml(d.title, d.avatar, "avatar").replace("46px", "80px")}
      <h2 style="margin:12px 0 4px;font-size:19px">${esc((isGroup ? "👥 " : "") + d.title)}</h2>
      <div style="color:var(--text-dim);font-size:13px;margin-bottom:16px">${isGroup ? chat.members.length + " a'zo" : ""}</div>
      <div style="text-align:left">
        ${isGroup ? `<div style="color:var(--text-dim);font-size:13px;margin-bottom:6px">A'zolar</div>` : ""}
        ${membersHtml}
      </div>
      ${isGroup ? `<button class="btn-accent" id="add-member" style="width:100%;margin-top:12px">+ A'zo qo'shish</button>
        <button class="leave-btn" id="leave-group" style="margin-top:8px">🚪 Guruhdan chiqish</button>` : ""}
    </div>`);
  $("m-close").onclick = closeModal;
  if (isGroup) {
    $("leave-group").onclick = async () => {
      await api(`/api/chats/${chat.id}/members/${state.me.id}`, { method: "DELETE" });
      state.chats = state.chats.filter((c) => c.id !== chat.id);
      delete state.messages[chat.id]; state.activeChatId = null;
      closeModal(); $("back-btn").onclick(); renderChatList();
    };
    $("add-member").onclick = () => openAddMember(chat);
  }
}

function openAddMember(chat) {
  showModal(`
    <div class="modal-head"><span>A'zo qo'shish</span><button class="icon-btn" id="m-close">✕</button></div>
    <div class="modal-body"><input class="text" id="am-search" placeholder="Qidirish..."><div id="am-results"></div></div>`);
  $("m-close").onclick = closeModal;
  let t;
  $("am-search").oninput = (e) => {
    clearTimeout(t); const q = e.target.value.trim(); if (!q) { $("am-results").innerHTML = ""; return; }
    t = setTimeout(async () => {
      const users = await api(`/api/users/search?q=${encodeURIComponent(q)}`);
      const memberIds = new Set(chat.members.map((m) => m.user.id));
      $("am-results").innerHTML = users.map((u) => `
        <div class="user-row" data-uid="${u.id}">${avatarHtml(u.display_name, u.avatar_url, "avatar sm")}
        <div><div class="u-name">${esc(u.display_name)}</div><div class="u-username">@${esc(u.username)}</div></div>
        ${memberIds.has(u.id) ? '<span class="u-check">✓</span>' : ""}</div>`).join("");
      $("am-results").querySelectorAll("[data-uid]").forEach((n) => n.onclick = async () => {
        const id = Number(n.dataset.uid); if (memberIds.has(id)) return;
        const updated = await api(`/api/chats/${chat.id}/members`, { method: "POST", body: { user_id: id } });
        const idx = state.chats.findIndex((c) => c.id === chat.id);
        if (idx !== -1) state.chats[idx] = updated;
        closeModal(); renderChatList();
      });
    }, 300);
  };
}

/* ================= START ================= */
setAuthMode("login");
if (state.token) {
  boot().catch(() => doLogout());
}
