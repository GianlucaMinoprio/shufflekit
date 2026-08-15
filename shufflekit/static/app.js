async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok || data.ok === false) throw new Error(data.error || res.statusText);
  return data;
}

const badge = document.getElementById("badge");
const verEl = document.getElementById("ver");
const deviceLine = document.getElementById("device-line");
const deviceMeta = document.getElementById("device-meta");
const spaceEl = document.getElementById("space");
const tracksEl = document.getElementById("tracks");
const countEl = document.getElementById("count");
const fileEl = document.getElementById("file");
const drop = document.getElementById("drop");
const statusEl = document.getElementById("status");

function fmtTime(ms) {
  const s = Math.max(0, Math.round((ms || 0) / 1000));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m + ":" + String(r).padStart(2, "0");
}

async function refresh() {
  const st = await api("/api/status");
  verEl.textContent = st.version ? "v" + st.version : "";
  if (!st.connected) {
    badge.textContent = "Offline";
    badge.classList.remove("on");
    deviceLine.textContent = "No shuffle";
    deviceMeta.textContent = "Plug it in.";
    spaceEl.textContent = "";
    tracksEl.innerHTML = "";
    countEl.textContent = "0";
    return;
  }
  badge.textContent = "Connected";
  badge.classList.add("on");
  deviceLine.textContent = st.volume || "IPOD";
  deviceMeta.textContent = st.serial || "";
  const gb = (n) => (n / 1e9).toFixed(1);
  spaceEl.textContent = gb(st.free_bytes) + " / " + gb(st.total_bytes) + " GB";

  const list = await api("/api/tracks");
  const rows = list.tracks || [];
  countEl.textContent = String(rows.length);
  tracksEl.innerHTML = "";
  for (const t of rows) {
    const tr = document.createElement("tr");
    if (!t.exists) tr.className = "missing";
    tr.innerHTML =
      '<td class="num">' + t.n + "</td>" +
      "<td>" + escapeHtml(t.name) + "</td>" +
      '<td class="num">' + fmtTime(t.duration_ms) + "</td>";
    tracksEl.appendChild(tr);
  }
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function setStatus(text) {
  statusEl.textContent = text || "";
}

document.getElementById("add").onclick = async () => {
  if (!fileEl.files.length) {
    setStatus("Pick files.");
    return;
  }
  const fd = new FormData();
  for (const f of fileEl.files) fd.append("files", f, f.name);
  setStatus("Writing…");
  try {
    const r = await api("/api/add", { method: "POST", body: fd });
    setStatus("Added " + r.added + ".");
    fileEl.value = "";
    await refresh();
  } catch (e) {
    setStatus(e.message);
  }
};

document.getElementById("orphans").onclick = () => runRebuild(true);
document.getElementById("rebuild").onclick = () => runRebuild(false);

async function runRebuild(orphans) {
  setStatus("Rebuilding…");
  try {
    const r = await api("/api/rebuild", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ orphans, voiceover: true }),
    });
    setStatus(r.tracks + " playable.");
    await refresh();
  } catch (e) {
    setStatus(e.message);
  }
}

["dragenter", "dragover"].forEach((ev) => {
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.add("over");
  });
});
["dragleave", "drop"].forEach((ev) => {
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.remove("over");
  });
});
drop.addEventListener("drop", (e) => {
  if (e.dataTransfer && e.dataTransfer.files.length) {
    fileEl.files = e.dataTransfer.files;
  }
});

refresh().catch((e) => {
  badge.textContent = "Error";
  deviceLine.textContent = "Server down";
  deviceMeta.textContent = e.message;
});
