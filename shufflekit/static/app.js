async function api(path, opts) {
  const res = await fetch(path, opts);
  const data = await res.json();
  if (!res.ok || data.ok === false) throw new Error(data.error || res.statusText);
  return data;
}

const deviceLine = document.getElementById("device-line");
const deviceMeta = document.getElementById("device-meta");
const tracksEl = document.getElementById("tracks");
const countEl = document.getElementById("count");
const verEl = document.getElementById("ver");
const fileEl = document.getElementById("file");
const drop = document.getElementById("drop");

async function refresh() {
  const st = await api("/api/status");
  verEl.textContent = "v" + (st.version || "");
  if (!st.connected) {
    deviceLine.textContent = "No shuffle mounted";
    deviceMeta.textContent = "Plug it in. Wait until you see a disk named IPOD, then refresh.";
    tracksEl.innerHTML = "";
    countEl.textContent = "0";
    return;
  }
  deviceLine.textContent = "Connected · " + st.volume;
  const gb = (n) => (n / 1e9).toFixed(2);
  deviceMeta.textContent =
    (st.serial ? "Serial " + st.serial + " · " : "") +
    gb(st.free_bytes) + " GB free of " + gb(st.total_bytes) +
    " · " + st.root;
  const list = await api("/api/tracks");
  tracksEl.innerHTML = "";
  countEl.textContent = String((list.tracks || []).length);
  for (const t of list.tracks || []) {
    const li = document.createElement("li");
    const sec = Math.round((t.duration_ms || 0) / 1000);
    li.textContent = t.name + "  " + sec + "s";
    if (!t.exists) {
      li.className = "missing";
      li.textContent += "  missing file";
    }
    tracksEl.appendChild(li);
  }
}

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

;["dragenter", "dragover"].forEach((ev) => {
  drop.addEventListener(ev, (e) => {
    e.preventDefault();
    drop.classList.add("over");
  });
});
;["dragleave", "drop"].forEach((ev) => {
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
  deviceLine.textContent = "UI backend is down";
  deviceMeta.textContent = e.message;
});
