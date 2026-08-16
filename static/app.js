const libraryEl = document.getElementById("library");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const searchResultsEl = document.getElementById("search-results");

function formatDuration(seconds) {
  if (!seconds) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

const NOW_PLAYING_KEY = "karaoke:nowPlaying";
const LIB_SCROLL_KEY = "karaoke:libScroll";

// Navigate into the player, remembering where we were in the library so we can
// restore the scroll position (and highlight the song) when the user comes back.
function goToPlayer(songId) {
  try {
    sessionStorage.setItem(LIB_SCROLL_KEY, String(window.scrollY));
  } catch (e) {
    /* non-critical */
  }
  window.location.href = `/player/${songId}`;
}

async function loadLibrary() {
  const res = await fetch("/api/library");
  const songs = await res.json();

  if (songs.length === 0) {
    libraryEl.innerHTML = "<p>No songs yet. Search for one below.</p>";
  } else {
    libraryEl.innerHTML = "";
    for (const song of songs) {
      libraryEl.appendChild(renderSongCard(song));
    }
  }

  renderNowPlayingBar(songs);
  restoreLibraryPosition();
}

// On returning from the player, jump back to the previous scroll position and
// briefly highlight the song that was open, so the app feels continuous.
function restoreLibraryPosition() {
  let lastOpened = null;
  try {
    lastOpened = JSON.parse(localStorage.getItem(NOW_PLAYING_KEY) || "null");
  } catch (e) {
    lastOpened = null;
  }
  if (lastOpened && lastOpened.id) {
    const card = libraryEl.querySelector(`[data-song-id="${CSS.escape(lastOpened.id)}"]`);
    if (card) card.classList.add("highlighted");
  }

  let scrollY = null;
  try {
    scrollY = sessionStorage.getItem(LIB_SCROLL_KEY);
  } catch (e) {
    scrollY = null;
  }
  if (scrollY !== null) {
    window.scrollTo(0, parseInt(scrollY, 10) || 0);
    try {
      sessionStorage.removeItem(LIB_SCROLL_KEY);
    } catch (e) {
      /* non-critical */
    }
  }
}

function renderNowPlayingBar(songs) {
  document.getElementById("now-playing-bar")?.remove();
  document.body.classList.remove("has-now-playing");

  let saved;
  try {
    saved = JSON.parse(localStorage.getItem(NOW_PLAYING_KEY) || "null");
  } catch (e) {
    saved = null;
  }
  if (!saved || !saved.id) return;

  // Only show the bar if the song still exists and is playable.
  const song = songs.find((s) => s.id === saved.id);
  if (!song || song.status !== "done") {
    localStorage.removeItem(NOW_PLAYING_KEY);
    return;
  }

  const bar = document.createElement("div");
  bar.className = "now-playing-bar";
  bar.id = "now-playing-bar";

  const inner = document.createElement("div");
  inner.className = "now-playing-inner";

  const icon = document.createElement("div");
  icon.className = "now-playing-icon";
  icon.textContent = "♪";

  const text = document.createElement("div");
  text.className = "now-playing-text";
  text.innerHTML = `<div class="now-playing-label">Now playing</div><div class="now-playing-title"></div>`;
  text.querySelector(".now-playing-title").textContent = song.title;
  text.addEventListener("click", () => goToPlayer(song.id));

  const resumeBtn = document.createElement("button");
  resumeBtn.className = "btn btn-sm";
  resumeBtn.textContent = "▶ Resume";
  resumeBtn.addEventListener("click", () => goToPlayer(song.id));

  const dismissBtn = document.createElement("button");
  dismissBtn.className = "now-playing-dismiss";
  dismissBtn.setAttribute("aria-label", "Dismiss");
  dismissBtn.innerHTML = "&times;";
  dismissBtn.addEventListener("click", () => {
    localStorage.removeItem(NOW_PLAYING_KEY);
    bar.remove();
    document.body.classList.remove("has-now-playing");
  });

  inner.appendChild(icon);
  inner.appendChild(text);
  inner.appendChild(resumeBtn);
  inner.appendChild(dismissBtn);
  bar.appendChild(inner);
  document.body.appendChild(bar);
  document.body.classList.add("has-now-playing");
}

// Inline-edit a song's title in place. Replaces the title element with a text
// input; Enter or blur saves, Escape cancels.
function startRename(song, titleEl) {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "rename-input";
  input.value = song.title;
  titleEl.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  const restore = () => {
    if (done) return;
    done = true;
    input.replaceWith(titleEl);
  };
  const save = async () => {
    if (done) return;
    const newTitle = input.value.trim();
    if (!newTitle || newTitle === song.title) {
      restore();
      return;
    }
    done = true;
    input.disabled = true;
    const res = await fetch("/api/rename-song", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ song_id: song.id, title: newTitle }),
    });
    const data = await res.json();
    if (data.error) {
      alert(`Error: ${data.error}`);
      input.replaceWith(titleEl);
      return;
    }
    song.title = newTitle;
    titleEl.textContent = newTitle;
    input.replaceWith(titleEl);
    // Keep the Now Playing bar label in sync if this is the current song.
    try {
      const np = JSON.parse(localStorage.getItem(NOW_PLAYING_KEY) || "null");
      if (np && np.id === song.id) {
        np.title = newTitle;
        localStorage.setItem(NOW_PLAYING_KEY, JSON.stringify(np));
        const npTitle = document.querySelector("#now-playing-bar .now-playing-title");
        if (npTitle) npTitle.textContent = newTitle;
      }
    } catch (e) {
      /* non-critical */
    }
  };

  input.addEventListener("keydown", (e) => {
    e.stopPropagation();
    if (e.key === "Enter") {
      e.preventDefault();
      save();
    } else if (e.key === "Escape") {
      e.preventDefault();
      restore();
    }
  });
  input.addEventListener("blur", save);
  input.addEventListener("click", (e) => e.stopPropagation());
}

function renderSongCard(song) {
  const card = document.createElement("div");
  card.className = "card song-card";
  card.dataset.songId = song.id;

  if (song.status === "done") {
    const playerLink = document.createElement("div");
    playerLink.className = "meta";
    playerLink.style.cursor = "pointer";
    const titleEl = document.createElement("div");
    titleEl.className = "title";
    titleEl.textContent = song.title;
    const subEl = document.createElement("div");
    subEl.className = "sub";
    subEl.textContent = "Ready";
    playerLink.appendChild(titleEl);
    playerLink.appendChild(subEl);
    playerLink.addEventListener("click", () => goToPlayer(song.id));
    card.appendChild(playerLink);

    // Add action buttons for completed songs
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "song-actions";

    if (song.active_job_id) {
      const statusSpan = document.createElement("span");
      statusSpan.className = "status-text";
      statusSpan.textContent = "Processing...";
      actionsDiv.appendChild(statusSpan);
      pollJob(song.active_job_id, null, actionsDiv);
      card.appendChild(actionsDiv);
      return card;
    }

    const exportToggleBtn = document.createElement("button");
    exportToggleBtn.textContent = "Export Video…";
    exportToggleBtn.className = "btn btn-sm";
    exportToggleBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      openExportModal(song);
    });
    actionsDiv.appendChild(exportToggleBtn);

    const renameBtn = document.createElement("button");
    renameBtn.textContent = "Rename";
    renameBtn.className = "btn btn-ghost btn-sm";
    renameBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      startRename(song, titleEl);
    });
    actionsDiv.appendChild(renameBtn);

    const researchBtn = document.createElement("button");
    researchBtn.textContent = "Re-search Lyrics";
    researchBtn.className = "btn btn-ghost btn-sm";
    researchBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      researchBtn.disabled = true;
      const res = await fetch("/api/research-lyrics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ song_id: song.id }),
      });
      const data = await res.json();
      if (data.error) {
        alert(`Error: ${data.error}`);
        researchBtn.disabled = false;
      } else {
        loadLibrary();
      }
    });
    actionsDiv.appendChild(researchBtn);

    const resyncBtn = document.createElement("button");
    resyncBtn.textContent = "Re-sync to Audio";
    resyncBtn.title = "Re-align lyric word timings to the actual audio using forced alignment";
    resyncBtn.className = "btn btn-ghost btn-sm";
    resyncBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      resyncBtn.disabled = true;
      resyncBtn.textContent = "Starting...";
      const res = await fetch("/api/resync-lyrics", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ song_id: song.id }),
      });
      const data = await res.json();
      if (data.error) {
        alert(`Error: ${data.error}`);
        resyncBtn.disabled = false;
        resyncBtn.textContent = "Re-sync to Audio";
        return;
      }
      loadLibrary();
    });
    actionsDiv.appendChild(resyncBtn);

    const deleteBtn = document.createElement("button");
    deleteBtn.textContent = "Delete";
    deleteBtn.className = "btn btn-danger btn-sm";
    deleteBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      if (!confirm(`Delete "${song.title}" and all related files?`)) return;
      const res = await fetch("/api/delete-song", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ song_id: song.id }),
      });
      const data = await res.json();
      if (data.error) {
        alert(`Error: ${data.error}`);
      } else {
        loadLibrary();
      }
    });
    actionsDiv.appendChild(deleteBtn);

    card.appendChild(actionsDiv);
    return card;
  }

  // In-progress song: show step checklist + resume/progress.
  const stepsList = document.createElement("ul");
  stepsList.className = "steps";
  for (const stepKey of song.step_order) {
    const li = document.createElement("li");
    const stepStatus = (song.steps || {})[stepKey] || "pending";
    li.className = `step step-${stepStatus}`;
    li.dataset.step = stepKey;
    li.innerHTML = `<span class="step-icon"></span><span class="step-label">${song.step_labels[stepKey]}</span>`;
    stepsList.appendChild(li);
  }

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.innerHTML = `<div class="title">${song.title}</div><div class="sub">In progress</div>`;
  meta.appendChild(stepsList);

  const actionEl = document.createElement("div");
  actionEl.className = "song-action";

  card.appendChild(meta);
  card.appendChild(actionEl);

  if (song.active_job_id) {
    actionEl.innerHTML = `<span class="status-text">Processing...</span>`;
    pollJob(song.active_job_id, stepsList, actionEl);
  } else {
    const checkLyricsDone = (song.steps || {}).check_lyrics === "done";
    const transcribePending = (song.steps || {}).transcribe === "pending";
    if (checkLyricsDone && transcribePending) {
      // Show lyrics decision UI: pick a candidate, search manually, or run WhisperX.
      const candidatesDiv = document.createElement("div");
      candidatesDiv.style.marginBottom = "0.75rem";

      const candidateList = document.createElement("div");
      candidateList.style.fontSize = "0.9rem";
      candidateList.style.marginBottom = "0.5rem";
      candidateList.style.maxHeight = "240px";
      candidateList.style.overflowY = "auto";

      function renderCandidateButtons(candidates) {
        candidateList.innerHTML = "";
        if (candidates.length === 0) {
          candidateList.innerHTML = "<em>No matches found.</em>";
          return;
        }
        for (const cand of candidates) {
          const btn = document.createElement("button");
          btn.style.display = "block";
          btn.style.width = "100%";
          btn.style.marginBottom = "0.25rem";
          btn.style.padding = "0.5rem";
          btn.style.textAlign = "left";
          btn.style.fontSize = "0.85rem";
          const sourceLabel = cand.source === "musixmatch" ? "Musixmatch" : "LrcLib";
          btn.textContent = `[${sourceLabel}] ${cand.artist_name} - ${cand.track_name}`;
          btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            btn.disabled = true;
            const res = await fetch("/api/select-lyrics", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ song_id: song.id, candidate_id: cand.id }),
            });
            if (res.ok) {
              const data = await res.json();
              if (data.job_id) {
                actionEl.innerHTML = `<span class="status-text">Processing...</span>`;
                pollJob(data.job_id, stepsList, actionEl);
              } else {
                loadLibrary();
              }
            } else {
              alert("Error selecting lyrics");
              btn.disabled = false;
            }
          });
          candidateList.appendChild(btn);
        }
      }

      candidatesDiv.innerHTML = "<strong>Select lyrics:</strong>";
      renderCandidateButtons(song.lyrics_candidates || []);
      candidatesDiv.appendChild(candidateList);

      // Manual search box
      const searchRow = document.createElement("div");
      searchRow.style.display = "flex";
      searchRow.style.gap = "0.25rem";
      searchRow.style.marginBottom = "0.5rem";

      const sourceSelect = document.createElement("select");
      sourceSelect.style.fontSize = "0.85rem";
      sourceSelect.addEventListener("click", (e) => e.stopPropagation());
      for (const [value, label] of [["musixmatch", "Musixmatch"], ["lrclib", "LrcLib"]]) {
        const opt = document.createElement("option");
        opt.value = value;
        opt.textContent = label;
        sourceSelect.appendChild(opt);
      }

      const searchInput = document.createElement("input");
      searchInput.type = "text";
      searchInput.placeholder = "Search lyrics database...";
      searchInput.style.flex = "1";
      searchInput.style.fontSize = "0.85rem";
      searchInput.addEventListener("click", (e) => e.stopPropagation());

      const searchBtn = document.createElement("button");
      searchBtn.textContent = "Search";

      async function runLyricsSearch() {
        const query = searchInput.value.trim();
        if (!query) return;
        searchBtn.disabled = true;
        searchBtn.textContent = "Searching...";
        const res = await fetch("/api/search-lyrics", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ song_id: song.id, query, source: sourceSelect.value }),
        });
        const data = await res.json();
        searchBtn.disabled = false;
        searchBtn.textContent = "Search";
        if (data.error) {
          alert(`Error: ${data.error}`);
          return;
        }
        renderCandidateButtons(data.candidates || []);
      }

      searchBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        runLyricsSearch();
      });
      searchInput.addEventListener("keydown", (e) => {
        e.stopPropagation();
        if (e.key === "Enter") {
          e.preventDefault();
          runLyricsSearch();
        }
      });

      searchRow.appendChild(sourceSelect);
      searchRow.appendChild(searchInput);
      searchRow.appendChild(searchBtn);
      candidatesDiv.appendChild(searchRow);

      const skipBtn = document.createElement("button");
      skipBtn.textContent = "Skip to WhisperX";
      skipBtn.style.marginTop = "0.5rem";
      skipBtn.style.marginRight = "0.5rem";
      skipBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        skipBtn.disabled = true;
        const res = await fetch("/api/transcribe", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ song_id: song.id }),
        });
        const data = await res.json();
        if (data.error) {
          actionEl.innerHTML = `<span class="status-text error">Error: ${data.error}</span>`;
          return;
        }
        actionEl.innerHTML = `<span class="status-text">Processing...</span>`;
        pollJob(data.job_id, stepsList, actionEl);
      });
      candidatesDiv.appendChild(skipBtn);

      actionEl.appendChild(candidatesDiv);
    } else {
      // Default: show Resume button
      const resumeBtn = document.createElement("button");
      resumeBtn.textContent = "Resume";
      resumeBtn.addEventListener("click", async (e) => {
        e.stopPropagation();
        resumeBtn.disabled = true;
        resumeBtn.textContent = "Starting...";
        const res = await fetch("/api/resume", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ song_id: song.id }),
        });
        const data = await res.json();
        if (data.error) {
          actionEl.innerHTML = `<span class="status-text error">Error: ${data.error}</span>`;
          return;
        }
        actionEl.innerHTML = `<span class="status-text">Processing...</span>`;
        pollJob(data.job_id, stepsList, actionEl);
      });
      actionEl.appendChild(resumeBtn);
    }
  }

  return card;
}

// ── Default export folder (persisted via IndexedDB as a directory handle) ──
const FS_DB_NAME = "karaoke-fs";
const FS_STORE = "handles";
const DEFAULT_DIR_KEY = "defaultExportDir";

function openFsDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(FS_DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(FS_STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbGet(key) {
  const db = await openFsDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(FS_STORE, "readonly");
    const req = tx.objectStore(FS_STORE).get(key);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function idbSet(key, value) {
  const db = await openFsDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(FS_STORE, "readwrite");
    tx.objectStore(FS_STORE).put(value, key);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getDefaultExportDir() {
  try {
    return (await idbGet(DEFAULT_DIR_KEY)) || null;
  } catch (e) {
    return null;
  }
}

async function setDefaultExportDir(handle) {
  try {
    await idbSet(DEFAULT_DIR_KEY, handle);
  } catch (e) {
    /* non-critical */
  }
}

// Returns true if we already have (or can silently regain) read-write access.
async function verifyDirPermission(handle) {
  if (!handle) return false;
  try {
    if ((await handle.queryPermission({ mode: "readwrite" })) === "granted") return true;
    if ((await handle.requestPermission({ mode: "readwrite" })) === "granted") return true;
  } catch (e) {
    /* handle may be stale (e.g. folder moved/deleted) */
  }
  return false;
}

const VIDEO_FONTS = ["Helvetica Neue", "Arial Black", "Arial", "Verdana", "Georgia", "Impact", "Futura", "Comic Sans", "Times New Roman"];
const VIDEO_BACKGROUNDS = [
  ["gradient", "Gradient"],
  ["blur", "Blurred Thumbnail"],
  ["solid", "Solid Color"],
  ["photo", "Custom Photo"],
];

function openExportModal(song) {
  let previewUrl = null;

  const overlay = document.createElement("div");
  overlay.className = "modal-overlay";

  const modal = document.createElement("div");
  modal.className = "modal";
  overlay.appendChild(modal);

  function close() {
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    document.removeEventListener("keydown", onKeydown);
    overlay.remove();
  }
  function onKeydown(e) {
    if (e.key === "Escape") close();
  }
  overlay.addEventListener("click", (e) => {
    if (e.target === overlay) close();
  });
  document.addEventListener("keydown", onKeydown);

  // Header
  const header = document.createElement("div");
  header.className = "modal-header";
  const h3 = document.createElement("h3");
  h3.textContent = `Export Video — ${song.title}`;
  const closeBtn = document.createElement("button");
  closeBtn.className = "modal-close";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.innerHTML = "&times;";
  closeBtn.addEventListener("click", close);
  header.appendChild(h3);
  header.appendChild(closeBtn);
  modal.appendChild(header);

  const row = (label) => {
    const r = document.createElement("div");
    r.className = "field-row";
    if (label) {
      const l = document.createElement("label");
      l.textContent = label;
      r.appendChild(l);
    }
    return r;
  };

  // Live preview (at top so settings changes are immediately visible)
  const previewImg = document.createElement("img");
  previewImg.className = "export-preview";
  previewImg.alt = "Video preview";
  const previewLoading = document.createElement("div");
  previewLoading.className = "status-text";
  previewLoading.textContent = "Loading preview…";
  modal.appendChild(previewImg);
  modal.appendChild(previewLoading);

  // Background select
  const bgRow = row("Background");
  const bgSelect = document.createElement("select");
  for (const [value, label] of VIDEO_BACKGROUNDS) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    bgSelect.appendChild(opt);
  }
  bgRow.appendChild(bgSelect);
  modal.appendChild(bgRow);

  // Photo upload (shown only when "Custom Photo" is selected)
  const photoRow = row("Photo");
  photoRow.style.display = "none";
  const photoInput = document.createElement("input");
  photoInput.type = "file";
  photoInput.accept = "image/jpeg,image/png";
  const photoStatus = document.createElement("span");
  photoStatus.className = "status-text";
  photoRow.appendChild(photoInput);
  photoRow.appendChild(photoStatus);
  modal.appendChild(photoRow);

  // Font select
  const fontRow = row("Font");
  const fontSelect = document.createElement("select");
  for (const f of VIDEO_FONTS) {
    const opt = document.createElement("option");
    opt.value = f;
    opt.textContent = f;
    if (f === "Helvetica Neue") opt.selected = true;
    fontSelect.appendChild(opt);
  }
  fontRow.appendChild(fontSelect);
  modal.appendChild(fontRow);

  // Font size
  const sizeRow = row("Font size");
  const sizeInput = document.createElement("input");
  sizeInput.type = "range";
  sizeInput.min = "24";
  sizeInput.max = "80";
  sizeInput.value = "48";
  const sizeValue = document.createElement("span");
  sizeValue.textContent = "48px";
  sizeValue.style.minWidth = "3rem";
  sizeRow.appendChild(sizeInput);
  sizeRow.appendChild(sizeValue);
  modal.appendChild(sizeRow);

  // Resolution
  const resRow = row("Resolution");
  const resSelect = document.createElement("select");
  for (const [value, label] of [["720p", "HD 720p (1280×720)"], ["1080p", "Full HD 1080p (1920×1080)"]]) {
    const opt = document.createElement("option");
    opt.value = value;
    opt.textContent = label;
    resSelect.appendChild(opt);
  }
  resRow.appendChild(resSelect);
  modal.appendChild(resRow);

  // Intro video — select from Video Exports folder (server-side) or upload a file.
  let introFile = null;       // File object from browser upload
  let introServerPath = null; // server-side path string (from dropdown)

  const introRow = row("Intro video");

  // Dropdown of videos already in the Video Exports folder.
  const introSelect = document.createElement("select");
  introSelect.style.maxWidth = "220px";
  const introNoneOpt = document.createElement("option");
  introNoneOpt.value = "";
  introNoneOpt.textContent = "None";
  introSelect.appendChild(introNoneOpt);
  // "Upload…" sentinel at the end so the user can bring their own file.
  const introUploadOpt = document.createElement("option");
  introUploadOpt.value = "__upload__";
  introUploadOpt.textContent = "Upload a file…";

  // Populate from server.
  (async () => {
    try {
      const res = await fetch("/api/intro-videos");
      const files = await res.json();
      for (const f of files) {
        const opt = document.createElement("option");
        opt.value = f.path;
        opt.textContent = f.name;
        introSelect.appendChild(opt);
      }
    } catch (e) { /* server may not have returned yet */ }
    introSelect.appendChild(introUploadOpt);
  })();

  // Hidden file input for manual upload.
  const introInput = document.createElement("input");
  introInput.type = "file";
  introInput.accept = "video/mp4,video/quicktime,video/x-matroska,video/avi,.mp4,.mov,.m4v,.mkv,.avi";
  introInput.style.display = "none";

  const introUploadLabel = document.createElement("span");
  introUploadLabel.className = "status-text";
  introUploadLabel.style.marginLeft = "0.5rem";

  introSelect.addEventListener("change", () => {
    if (introSelect.value === "__upload__") {
      introInput.click();
    } else {
      introServerPath = introSelect.value || null;
      introFile = null;
      introUploadLabel.textContent = "";
    }
  });

  introInput.addEventListener("change", () => {
    introFile = introInput.files[0] || null;
    introServerPath = null;
    if (introFile) {
      introUploadLabel.textContent = introFile.name;
    } else {
      introSelect.value = "";
      introUploadLabel.textContent = "";
    }
  });

  introRow.appendChild(introSelect);
  introRow.appendChild(introInput);
  introRow.appendChild(introUploadLabel);
  modal.appendChild(introRow);

  // Default export folder (only relevant in browsers that support the File
  // System Access API; otherwise hidden and we fall back to a download link).
  const folderRow = row("Save to");
  const folderLabel = document.createElement("span");
  folderLabel.className = "status-text";
  folderLabel.textContent = "Choose location when exporting";
  const folderBtn = document.createElement("button");
  folderBtn.className = "btn btn-ghost btn-sm";
  folderBtn.textContent = "Set default folder…";
  folderRow.appendChild(folderLabel);
  folderRow.appendChild(folderBtn);
  modal.appendChild(folderRow);

  if (window.showSaveFilePicker && window.showDirectoryPicker) {
    (async () => {
      const dir = await getDefaultExportDir();
      if (dir && (await verifyDirPermission(dir))) {
        folderLabel.textContent = `Default: ${dir.name}`;
      }
    })();

    folderBtn.addEventListener("click", async (e) => {
      e.stopPropagation();
      try {
        const dir = await window.showDirectoryPicker({ mode: "readwrite" });
        await setDefaultExportDir(dir);
        folderLabel.textContent = `Default: ${dir.name}`;
      } catch (e) {
        /* user cancelled */
      }
    });
  } else {
    folderRow.style.display = "none";
  }

  async function refreshPreview() {
    previewLoading.style.display = "";
    previewLoading.textContent = "Loading preview…";
    const res = await fetch("/api/preview-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        song_id: song.id,
        background: bgSelect.value,
        font: fontSelect.value,
        font_size: parseInt(sizeInput.value, 10),
      }),
    });
    if (!res.ok) {
      previewLoading.textContent = "Preview failed to load.";
      return;
    }
    const blob = await res.blob();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(blob);
    previewImg.src = previewUrl;
    previewLoading.style.display = "none";
  }

  bgSelect.addEventListener("change", () => {
    photoRow.style.display = bgSelect.value === "photo" ? "" : "none";
    refreshPreview();
  });
  fontSelect.addEventListener("change", refreshPreview);
  sizeInput.addEventListener("input", () => {
    sizeValue.textContent = `${sizeInput.value}px`;
  });
  sizeInput.addEventListener("change", refreshPreview);

  photoInput.addEventListener("change", async () => {
    const file = photoInput.files[0];
    if (!file) return;
    photoStatus.textContent = "Uploading…";
    const formData = new FormData();
    formData.append("song_id", song.id);
    formData.append("file", file);
    const res = await fetch("/api/upload-video-background", { method: "POST", body: formData });
    const data = await res.json();
    if (data.error) {
      photoStatus.textContent = `Error: ${data.error}`;
      return;
    }
    photoStatus.textContent = "Uploaded.";
    refreshPreview();
  });

  // Footer: export button + status
  const footer = document.createElement("div");
  footer.className = "export-footer";
  const exportBtn = document.createElement("button");
  exportBtn.className = "btn";
  exportBtn.textContent = "Export Video";
  const statusSpan = document.createElement("span");
  statusSpan.className = "status-text";
  footer.appendChild(exportBtn);
  footer.appendChild(statusSpan);
  modal.appendChild(footer);

  function appendDownloadLink() {
    const link = document.createElement("a");
    link.href = `/library/${song.id}/karaoke.mp4`;
    link.textContent = "Download Video";
    link.download = `${song.title}.mp4`;
    footer.appendChild(link);
  }

  exportBtn.addEventListener("click", async () => {
    // Ask where to save *before* rendering starts (File System Access API),
    // pre-filling the location with the chosen default folder if one is set.
    let fileHandle = null;
    if (window.showSaveFilePicker) {
      let startIn;
      const dir = await getDefaultExportDir();
      if (dir && (await verifyDirPermission(dir))) startIn = dir;
      try {
        fileHandle = await window.showSaveFilePicker({
          suggestedName: `${song.title}.mp4`,
          startIn,
          types: [{ description: "MP4 video", accept: { "video/mp4": [".mp4"] } }],
        });
      } catch (e) {
        if (e && e.name === "AbortError") return;
        fileHandle = null;
      }
    }

    exportBtn.disabled = true;
    exportBtn.textContent = "Starting…";
    statusSpan.textContent = "";

    // Register intro video (server-side path or browser upload) before rendering.
    let introVideoId = null;
    if (introServerPath) {
      // File already on disk — just register its path with the server.
      try {
        const res2 = await fetch("/api/set-intro-by-path", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: introServerPath }),
        });
        const d2 = await res2.json();
        if (d2.error) {
          statusSpan.textContent = `Intro error: ${d2.error}`;
          exportBtn.disabled = false; exportBtn.textContent = "Export Video"; return;
        }
        introVideoId = d2.temp_id;
      } catch (e) {
        statusSpan.textContent = "Could not register intro. Check server.";
        exportBtn.disabled = false; exportBtn.textContent = "Export Video"; return;
      }
    } else if (introFile) {
      // User picked a file to upload.
      statusSpan.textContent = "Uploading intro video…";
      const fd = new FormData();
      fd.append("file", introFile);
      try {
        const upRes = await fetch("/api/upload-intro-video", { method: "POST", body: fd });
        const upData = await upRes.json();
        if (upData.error) {
          statusSpan.textContent = `Intro upload failed: ${upData.error}`;
          exportBtn.disabled = false; exportBtn.textContent = "Export Video"; return;
        }
        introVideoId = upData.temp_id;
      } catch (e) {
        statusSpan.textContent = "Intro upload failed. Check connection.";
        exportBtn.disabled = false; exportBtn.textContent = "Export Video"; return;
      }
    }

    const res = await fetch("/api/export-video", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        song_id: song.id,
        background: bgSelect.value,
        font: fontSelect.value,
        font_size: parseInt(sizeInput.value, 10),
        resolution: resSelect.value,
        intro_video_id: introVideoId,
      }),
    });
    const data = await res.json();
    if (data.error) {
      alert(`Error: ${data.error}`);
      exportBtn.disabled = false;
      exportBtn.textContent = "Export Video";
      return;
    }
    statusSpan.textContent = "Rendering video…";

    const interval = setInterval(async () => {
      const jres = await fetch(`/api/jobs/${data.job_id}`);
      const job = await jres.json();
      if (job.status === "running") {
        statusSpan.textContent = job.stage || "Rendering video…";
      } else if (job.status === "done") {
        clearInterval(interval);
        if (fileHandle) {
          statusSpan.textContent = "Saving…";
          try {
            const vres = await fetch(`/library/${song.id}/karaoke.mp4`);
            const blob = await vres.blob();
            const writable = await fileHandle.createWritable();
            await writable.write(blob);
            await writable.close();
            statusSpan.textContent = "Saved.";
          } catch (e) {
            statusSpan.textContent = "Couldn't save automatically — use the link below.";
            appendDownloadLink();
          }
        } else {
          statusSpan.textContent = "Done.";
          appendDownloadLink();
        }
        exportBtn.disabled = false;
        exportBtn.textContent = "Export Video";
      } else if (job.status === "error") {
        clearInterval(interval);
        statusSpan.textContent = `Error: ${job.error}`;
        exportBtn.disabled = false;
        exportBtn.textContent = "Export Video";
      }
    }, 2000);
  });

  document.body.appendChild(overlay);
  refreshPreview();
}

function markStepStatus(stepsList, stepKey, status) {
  const li = stepsList.querySelector(`[data-step="${stepKey}"]`);
  if (!li) return;
  li.className = `step step-${status}`;
}

function pollJob(jobId, stepsList, actionEl) {
  const interval = setInterval(async () => {
    const res = await fetch(`/api/jobs/${jobId}`);
    const job = await res.json();

    if (job.status === "running") {
      const statusEl = actionEl.querySelector(".status-text");
      if (statusEl) statusEl.textContent = `${job.stage}...`;

      // Mark all steps before the current one as done, current as active.
      if (stepsList) {
        let reached = false;
        for (const li of stepsList.querySelectorAll(".step")) {
          const label = li.querySelector(".step-label").textContent;
          if (label === job.stage) {
            li.className = "step step-active";
            reached = true;
          } else if (!reached) {
            li.className = "step step-done";
          }
        }
      }
    } else if (job.status === "done") {
      clearInterval(interval);
      loadLibrary();
    } else if (job.status === "error") {
      clearInterval(interval);
      actionEl.innerHTML = `<span class="status-text error">Error: ${job.error}</span>`;
    }
  }, 2000);
}

searchForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const query = searchInput.value.trim();
  if (!query) return;

  searchResultsEl.innerHTML = "Searching...";
  try {
    const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
    const results = await res.json();
    if (results.error) {
      searchResultsEl.innerHTML = `<p>Error: ${results.error}</p>`;
      return;
    }
    renderSearchResults(results);
  } catch (err) {
    searchResultsEl.innerHTML = `<p>Error: ${err}</p>`;
  }
});

function renderSearchResults(results) {
  searchResultsEl.innerHTML = "";
  for (const video of results) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <img src="${video.thumbnail || ""}" alt="">
      <div class="meta">
        <div class="title">${video.title}</div>
        <div class="sub">${video.channel || ""} &middot; ${formatDuration(video.duration)}</div>
      </div>
    `;
    card.addEventListener("click", () => startProcessing(video));
    searchResultsEl.appendChild(card);
  }
}

async function startProcessing(video) {
  searchResultsEl.innerHTML = "";

  await fetch("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: video.url, title: video.title }),
  });

  loadLibrary();
}

document.getElementById("quit-btn").addEventListener("click", async () => {
  if (!confirm("Quit the Karaoke app?")) return;
  await fetch("/api/quit", { method: "POST" });
  document.body.innerHTML = "<h1>App stopped. You can close this tab.</h1>";
});

loadLibrary();
