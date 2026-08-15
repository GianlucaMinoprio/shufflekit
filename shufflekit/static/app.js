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

/* --- Apple Music playlists --- */
const plList = document.getElementById("playlist-list");
const plDetail = document.getElementById("pl-detail");
const plRecord = document.getElementById("pl-record");
const plStatus = document.getElementById("pl-status");
const plProgress = document.getElementById("pl-progress");
const plBar = document.getElementById("pl-bar");
let selectedPlaylist = null;

async function loadPlaylists() {
  plList.innerHTML = '<p class="muted">Loading…</p>';
  try {
    const data = await api("/api/playlists");
    if (data.error) {
      plList.innerHTML = '<p class="muted">' + escapeHtml(data.error) + "</p>";
      return;
    }
    if (!data.playlists || data.playlists.length === 0) {
      plList.innerHTML = '<p class="muted">No playlists. Is Music.app running?</p>';
      return;
    }
    plList.innerHTML = "";
    for (const pl of data.playlists) {
      const row = document.createElement("div");
      row.className = "pl-row";
      const fc = pl.file_tracks || 0;
      const sc = pl.stream_tracks || 0;
      const meta = fc > 0 ? fc + " copyable, " + sc + " streams" : sc + " streams (real-time)";
      row.innerHTML =
        '<span class="pl-name">' + escapeHtml(pl.name) + "</span>" +
        '<span class="pl-meta">' + pl.tracks + " tracks · " + meta + "</span>";
      row.onclick = () => {
        document.querySelectorAll(".pl-row").forEach(r => r.classList.remove("selected"));
        row.classList.add("selected");
        selectedPlaylist = pl.name;
        plDetail.classList.remove("hidden");
        plStatus.textContent = "";
        plProgress.classList.add("hidden");
        plBar.style.width = "0%";
        plRecord.textContent = fc > 0 && sc > 0 ? "Copy + record" : fc > 0 ? "Copy to shuffle" : "Record to shuffle";
      };
      plList.appendChild(row);
    }
  } catch (e) {
    plList.innerHTML = '<p class="muted">' + escapeHtml(e.message) + "</p>";
  }
}

document.getElementById("pl-refresh").onclick = loadPlaylists;

plRecord.onclick = async () => {
  if (!selectedPlaylist) return;
  plRecord.disabled = true;
  plProgress.classList.remove("hidden");
  plBar.style.width = "0%";
  plStatus.textContent = "Starting…";
  try {
    await api("/api/record-playlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ playlist: selectedPlaylist }),
    });
    // Poll progress
    const poll = setInterval(async () => {
      try {
        const p = await api("/api/record-progress");
        if (p.total > 0) plBar.style.width = Math.round(p.done / p.total * 100) + "%";
        plStatus.textContent = p.status || "";
        if (!p.active) {
          clearInterval(poll);
          plRecord.disabled = false;
          await refresh();
        }
      } catch {}
    }, 2000);
  } catch (e) {
    plStatus.textContent = e.message;
    plRecord.disabled = false;
  }
};

loadPlaylists().catch(() => {});
