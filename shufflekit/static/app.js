async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok || data.ok === false) throw new Error(data.error || res.statusText);
  return data;
}

// --- Elements ---
const deviceLine = document.getElementById("device-line");
const deviceMeta = document.getElementById("device-meta");
const deviceLed = document.getElementById("device-led");
const tracksEl = document.getElementById("tracks");
const countEl = document.getElementById("count");
const verEl = document.getElementById("ver");
const fileEl = document.getElementById("file");
const drop = document.getElementById("drop");
const playlistList = document.getElementById("playlist-list");
const playlistDetail = document.getElementById("playlist-detail");
const playlistInfo = document.getElementById("playlist-info");
const recordBtn = document.getElementById("record-playlist");
const recordProgress = document.getElementById("record-progress");
const recordBar = document.getElementById("record-bar");
const recordStatus = document.getElementById("record-status");

let selectedPlaylist = null;

// --- Status ---
async function refresh() {
  const st = await api("/api/status");
  verEl.textContent = "v" + (st.version || "");
  if (!st.connected) {
    deviceLine.textContent = "No shuffle mounted";
    deviceMeta.textContent = "Plug it in. Wait until you see a disk named IPOD, then refresh.";
    deviceLed.className = "status-dot";
    tracksEl.innerHTML = "";
    countEl.textContent = "0";
    return;
  }
  deviceLine.textContent = "Connected · " + st.volume;
  deviceLed.className = "status-dot connected";
  const gb = (n) => (n / 1e9).toFixed(2);
  deviceMeta.textContent =
    (st.serial ? "Serial " + st.serial + " · " : "") +
    gb(st.free_bytes) + " GB free of " + gb(st.total_bytes);
  const list = await api("/api/tracks");
  tracksEl.innerHTML = "";
  countEl.textContent = String((list.tracks || []).length);
  for (const t of list.tracks || []) {
    const li = document.createElement("li");
    const sec = Math.round((t.duration_ms || 0) / 1000);
    li.textContent = t.name + "  " + sec + "s";
    if (!t.exists) {
      li.className = "missing";
      li.textContent += "  (missing file)";
    }
    tracksEl.appendChild(li);
  }
}

// --- Playlists ---
async function loadPlaylists() {
  playlistList.innerHTML = '<p class="text-sm text-muted">Loading…</p>';
  try {
    const data = await api("/api/playlists");
    if (!data.playlists || data.playlists.length === 0) {
      playlistList.innerHTML = '<p class="text-sm text-muted">No playlists found. Is Music.app running?</p>';
      return;
    }
    playlistList.innerHTML = "";
    for (const pl of data.playlists) {
      const row = document.createElement("div");
      row.className = "playlist-row";
      const left = document.createElement("span");
      left.className = "text-sm";
      const fileCount = pl.file_tracks || 0;
      const streamCount = pl.stream_tracks || 0;
      const badge = fileCount > 0 ? fileCount + " copyable" : "streams only";
      left.textContent = pl.name + "  ·  " + pl.tracks + " tracks (" + badge + ")";
      row.appendChild(left);
      row.onclick = () => selectPlaylist(pl.name, fileCount, streamCount, row);
      playlistList.appendChild(row);
    }
  } catch (e) {
    playlistList.innerHTML = '<p class="text-sm text-muted">Error: ' + e.message + '</p>';
  }
}

function selectPlaylist(name, fileCount, streamCount, rowEl) {
  selectedPlaylist = name;
  document.querySelectorAll(".playlist-row").forEach(r => r.classList.remove("selected"));
  rowEl.classList.add("selected");
  playlistDetail.classList.remove("hidden");
  if (fileCount > 0) {
    playlistInfo.textContent = fileCount + " copyable + " + streamCount + " DRM streams";
    recordBtn.textContent = fileCount > 0 && streamCount > 0 ? "Copy + record to shuffle" : "Copy to shuffle";
  } else {
    playlistInfo.textContent = streamCount + " DRM streams (real-time recording)";
    recordBtn.textContent = "Record to shuffle";
  }
}

recordBtn.onclick = async () => {
  if (!selectedPlaylist) return;
  recordProgress.classList.remove("hidden");
  recordBtn.disabled = true;
  recordBar.style.width = "0%";
  recordStatus.textContent = "Starting…";
  try {
    const res = await api("/api/record-playlist", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ playlist: selectedPlaylist }),
    });
    recordBar.style.width = "100%";
    recordStatus.textContent = "Done. Added " + (res.added || 0) + " tracks. Playable " + (res.tracks || 0) + ".";
    await refresh();
  } catch (e) {
    recordStatus.textContent = "Error: " + e.message;
  }
  recordBtn.disabled = false;
};

document.getElementById("refresh-playlists").onclick = loadPlaylists;

// --- Add files ---
document.getElementById("add").onclick = async () => {
  const status = document.getElementById("add-status");
  if (!fileEl.files.length) {
    status.textContent = "Pick files first";
    return;
  }
  const fd = new FormData();
  for (const f of fileEl.files) fd.append("files", f, f.name);
  status.textContent = "Writing…";
  try {
    const r = await api("/api/add", { method: "POST", body: fd });
    status.textContent = "Added " + r.added + ". Playable " + r.tracks + ".";
    fileEl.value = "";
    await refresh();
  } catch (e) {
    status.textContent = e.message;
  }
};

// --- Rebuild ---
document.getElementById("orphans").onclick = () => runRebuild(true, "rebuild-status");
document.getElementById("rebuild").onclick = () => runRebuild(false, "rebuild-status");

async function runRebuild(orphans, id) {
  const status = document.getElementById(id);
  status.textContent = "Rebuilding…";
  try {
    const r = await api("/api/rebuild", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ orphans, voiceover: true }),
    });
    status.textContent = "Playable " + r.tracks + ".";
    await refresh();
  } catch (e) {
    status.textContent = e.message;
  }
}

// --- Drag and drop ---
["dragenter", "dragover"].forEach((ev) => {
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); });
});
["dragleave", "drop"].forEach((ev) => {
  drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); });
});
drop.addEventListener("drop", (e) => {
  if (e.dataTransfer && e.dataTransfer.files.length) {
    fileEl.files = e.dataTransfer.files;
  }
});

// --- Init ---
refresh().catch((e) => {
  deviceLine.textContent = "UI backend is down";
  deviceMeta.textContent = e.message;
});
loadPlaylists().catch(() => {});
