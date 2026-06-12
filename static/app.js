const libraryEl = document.getElementById("library");
const searchForm = document.getElementById("search-form");
const searchInput = document.getElementById("search-input");
const searchResultsEl = document.getElementById("search-results");
const jobStatusEl = document.getElementById("job-status");
const jobStageEl = document.getElementById("job-stage");

function formatDuration(seconds) {
  if (!seconds) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

async function loadLibrary() {
  const res = await fetch("/api/library");
  const songs = await res.json();

  if (songs.length === 0) {
    libraryEl.innerHTML = "<p>No songs yet. Search for one below.</p>";
    return;
  }

  libraryEl.innerHTML = "";
  for (const song of songs) {
    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="meta">
        <div class="title">${song.title}</div>
        <div class="sub">Ready</div>
      </div>
    `;
    card.addEventListener("click", () => {
      // Placeholder: navigate to the player view for this song.
      window.location.href = `/library/${song.id}/`;
    });
    libraryEl.appendChild(card);
  }
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
  jobStatusEl.classList.remove("hidden");
  jobStageEl.textContent = "Queued...";

  const res = await fetch("/api/process", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url: video.url, title: video.title }),
  });
  const { job_id } = await res.json();
  pollJob(job_id);
}

function pollJob(jobId) {
  const interval = setInterval(async () => {
    const res = await fetch(`/api/jobs/${jobId}`);
    const job = await res.json();

    if (job.status === "running") {
      jobStageEl.textContent = `Processing: ${job.stage}...`;
    } else if (job.status === "queued") {
      jobStageEl.textContent = "Queued...";
    } else if (job.status === "done") {
      jobStageEl.textContent = "Done!";
      clearInterval(interval);
      setTimeout(() => {
        jobStatusEl.classList.add("hidden");
        loadLibrary();
      }, 1000);
    } else if (job.status === "error") {
      jobStageEl.textContent = `Error: ${job.error}`;
      clearInterval(interval);
    }
  }, 2000);
}

document.getElementById("quit-btn").addEventListener("click", async () => {
  if (!confirm("Quit the Karaoke app?")) return;
  await fetch("/api/quit", { method: "POST" });
  document.body.innerHTML = "<h1>App stopped. You can close this tab.</h1>";
});

loadLibrary();
