import { PitchDetector } from "https://esm.sh/pitchy@4.1.0";

const songId = window.SONG_ID;

// Record this song as the "now playing" track so the Library can offer a
// persistent bar to jump straight back here.
try {
  localStorage.setItem(
    "karaoke:nowPlaying",
    JSON.stringify({ id: songId, title: window.SONG_TITLE || "" })
  );
} catch (e) {
  /* localStorage may be unavailable; the bar is a nicety, not critical */
}

// Inline title rename on the player page.
(function initTitleRename() {
  const titleEl = document.getElementById("song-title");
  const renameBtn = document.getElementById("rename-title-btn");
  if (!titleEl || !renameBtn) return;

  async function commitRename(newTitle, input) {
    newTitle = newTitle.trim();
    const current = titleEl.textContent;
    input.replaceWith(titleEl);
    if (!newTitle || newTitle === current) return;

    const res = await fetch("/api/rename-song", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ song_id: songId, title: newTitle }),
    });
    const data = await res.json();
    if (data.error) { alert(`Rename failed: ${data.error}`); return; }

    titleEl.textContent = newTitle;
    document.title = `${newTitle} - Karaoke`;
    window.SONG_TITLE = newTitle;
    try {
      localStorage.setItem("karaoke:nowPlaying", JSON.stringify({ id: songId, title: newTitle }));
    } catch (e) {}
  }

  function startRename() {
    const input = document.createElement("input");
    input.type = "text";
    input.className = "song-title-input";
    input.value = titleEl.textContent;
    titleEl.replaceWith(input);
    input.focus();
    input.select();
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") { e.preventDefault(); commitRename(input.value, input); }
      if (e.key === "Escape") { input.replaceWith(titleEl); }
    });
    input.addEventListener("blur", () => commitRename(input.value, input));
  }

  renameBtn.addEventListener("click", (e) => { e.stopPropagation(); startRename(); });
  titleEl.addEventListener("dblclick", startRename);
})();

const audio = document.getElementById("audio");
const playBtn = document.getElementById("play-btn");
const micBtn = document.getElementById("mic-btn");
const canvas = document.getElementById("visualizer");
const lyricsEl = document.getElementById("lyrics");
const pitchNeedle = document.getElementById("pitch-needle");
const pitchLabel = document.getElementById("pitch-label");
const scoreDisplay = document.getElementById("score-display");
const scoreValue = document.getElementById("score-value");
const seekBar = document.getElementById("seek-bar");
const seekProgress = document.getElementById("seek-progress");
const seekHandle = document.getElementById("seek-handle");
const timeCurrent = document.getElementById("time-current");
const timeTotal = document.getElementById("time-total");
const syncToggleBtn = document.getElementById("sync-toggle-btn");
const syncPanel = document.getElementById("sync-panel");
const syncOffsetSlider = document.getElementById("sync-offset-slider");
const syncOffsetValue = document.getElementById("sync-offset-value");
const syncOffsetSaveBtn = document.getElementById("sync-offset-save-btn");
const tapSyncBtn = document.getElementById("tap-sync-btn");
const tapSyncHint = document.getElementById("tap-sync-hint");

let audioCtx = null;
let analyser = null;
let micAnalyser = null;
let micDetector = null;
let micBuffer = null;
let micSampleRate = 44100;

let wordEls = [];
let baseTimings = []; // [{ el, start, end }] original timings, for the offset slider
let segmentGroups = []; // [{ start, end, groups: [word-group elements] }] for tap-sync
let referencePitch = null; // { times, f0, voiced }
let pitchHopSeconds = 0;

let scoreHits = 0;
let scoreTotal = 0;

// ---------------------------------------------------------------------------
// Load lyrics + reference pitch data
// ---------------------------------------------------------------------------

async function loadData() {
  const [timestamps, pitch] = await Promise.all([
    fetch(`/library/${songId}/timestamps.json`).then((r) => r.json()),
    fetch(`/library/${songId}/pitch.json`).then((r) => r.json()),
  ]);

  referencePitch = pitch;
  if (pitch.times.length > 1) {
    pitchHopSeconds = pitch.times[1] - pitch.times[0];
  }

  renderLyrics(timestamps);
}

// ---------------------------------------------------------------------------
// Syllable splitting: rough heuristic so karaoke highlighting can move
// syllable-by-syllable instead of jumping a whole word at once.
// ---------------------------------------------------------------------------

const VOWELS = "aeiouyAEIOUY";

function coreSyllables(word) {
  if (word.length <= 3) return [word];
  const syllables = [];
  let start = 0;
  let i = 0;
  while (i < word.length) {
    if (VOWELS.includes(word[i])) {
      let j = i + 1;
      while (j < word.length && VOWELS.includes(word[j])) j++;
      i = j;
      let k = i;
      while (k < word.length && !VOWELS.includes(word[k])) k++;
      const consonants = k - i;
      let breakPoint;
      if (k >= word.length) {
        breakPoint = word.length;
      } else if (consonants <= 1) {
        breakPoint = i;
      } else {
        breakPoint = i + Math.floor(consonants / 2);
      }
      syllables.push(word.slice(start, breakPoint));
      start = breakPoint;
      i = breakPoint;
    } else {
      i++;
    }
  }
  if (start < word.length) {
    if (syllables.length > 0) {
      syllables[syllables.length - 1] += word.slice(start);
    } else {
      syllables.push(word.slice(start));
    }
  }
  return syllables.length > 0 ? syllables : [word];
}

function splitSyllables(word) {
  const match = word.match(/^([^a-zA-Z]*)([a-zA-Z']*)([^a-zA-Z]*)$/);
  if (!match || !match[2]) return [word];
  const [, prefix, core, suffix] = match;
  const syllables = coreSyllables(core);
  syllables[0] = prefix + syllables[0];
  syllables[syllables.length - 1] += suffix;
  return syllables;
}

// Split a word's [start, end] time range across its syllables, proportional
// to syllable length.
function buildSyllableTimings(word) {
  const syllables = splitSyllables(word.word);
  const totalLen = syllables.reduce((s, x) => s + x.length, 0) || 1;
  const duration = word.end - word.start;
  const timings = [];
  let t = word.start;
  for (let idx = 0; idx < syllables.length; idx++) {
    const isLast = idx === syllables.length - 1;
    const segEnd = isLast ? word.end : t + duration * (syllables[idx].length / totalLen);
    timings.push({ text: syllables[idx], start: t, end: segEnd });
    t = segEnd;
  }
  return timings;
}

// ---------------------------------------------------------------------------
// Countdown dots: during long instrumental gaps, show "..." with each dot
// lighting up in turn so the singer knows when the next word starts.
// ---------------------------------------------------------------------------

const GAP_THRESHOLD = 3.0; // seconds - gaps longer than this get countdown dots
const DOT_COUNT = 3;
const DOT_DURATION = 1.0; // seconds each dot stays highlighted

function addCountdownDots(container, nextWordStart) {
  for (let i = DOT_COUNT; i >= 1; i--) {
    const dotEnd = nextWordStart - (i - 1) * DOT_DURATION;
    const dotStart = dotEnd - DOT_DURATION;
    const span = document.createElement("span");
    span.className = "dot";
    span.textContent = "•";
    span.dataset.start = dotStart;
    span.dataset.end = dotEnd;
    span.addEventListener("click", () => {
      if (tapSyncActive) {
        registerTap();
      } else {
        seekTo(dotStart);
      }
    });
    container.appendChild(span);
    wordEls.push(span);
    baseTimings.push({ el: span, start: dotStart, end: dotEnd });
  }
}

function renderLyrics(timestamps) {
  lyricsEl.innerHTML = "";
  wordEls = [];
  baseTimings = [];
  segmentGroups = [];

  let prevEnd = 0;

  for (const segment of timestamps.segments || []) {
    const segWords = (segment.words || []).filter(
      (w) => w.start !== undefined && w.end !== undefined
    );
    if (segWords.length === 0) continue;

    const gap = segWords[0].start - prevEnd;
    if (gap >= GAP_THRESHOLD) {
      addCountdownDots(lyricsEl, segWords[0].start);
    }

    const lineGroups = [];
    for (const word of segWords) {
      const group = document.createElement("span");
      group.className = "word-group";
      for (const syl of buildSyllableTimings(word)) {
        const span = document.createElement("span");
        span.className = "syllable";
        span.textContent = syl.text;
        span.dataset.start = syl.start;
        span.dataset.end = syl.end;
        span.addEventListener("click", () => {
          if (tapSyncActive) {
            registerTap();
          } else {
            seekTo(parseFloat(span.dataset.start));
          }
        });
        group.appendChild(span);
        wordEls.push(span);
        baseTimings.push({ el: span, start: syl.start, end: syl.end });
      }
      lyricsEl.appendChild(group);
      lineGroups.push(group);

      prevEnd = word.end;
    }

    segmentGroups.push({ start: segWords[0].start, end: segment.end, groups: lineGroups });

    // line break between segments
    lyricsEl.appendChild(document.createElement("br"));
  }

  // Reset any in-progress fine-tuning UI state for the freshly rendered lyrics.
  syncOffsetSlider.value = "0";
  syncOffsetValue.textContent = "0.00s";
}

// ---------------------------------------------------------------------------
// Seeking: click/drag the progress bar, or click a word to jump there
// ---------------------------------------------------------------------------

function seekTo(time) {
  const target = Math.max(0, Math.min(time, audio.duration || time));
  audio.currentTime = target;
  updateLyrics(target);
  updateSeekUI();
}

function formatTime(seconds) {
  if (!isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function updateSeekUI() {
  const duration = audio.duration || 0;
  const pct = duration > 0 ? (audio.currentTime / duration) * 100 : 0;
  seekProgress.style.width = `${pct}%`;
  seekHandle.style.left = `${pct}%`;
  timeCurrent.textContent = formatTime(audio.currentTime);
  timeTotal.textContent = formatTime(duration);
}

function seekFromPointerEvent(e) {
  const rect = seekBar.getBoundingClientRect();
  const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
  const pct = rect.width > 0 ? x / rect.width : 0;
  const duration = audio.duration || 0;
  seekTo(pct * duration);
}

let isSeeking = false;

seekBar.addEventListener("pointerdown", (e) => {
  isSeeking = true;
  seekFromPointerEvent(e);
});

window.addEventListener("pointermove", (e) => {
  if (isSeeking) seekFromPointerEvent(e);
});

window.addEventListener("pointerup", () => {
  isSeeking = false;
});

audio.addEventListener("loadedmetadata", updateSeekUI);
audio.addEventListener("durationchange", updateSeekUI);

// WhisperX forced alignment tends to mark word onsets slightly after the
// audio actually starts the sound. Shift the highlight check forward in
// time by this much to compensate. Tune if highlighting still feels off.
const SYNC_LEAD_TIME = 0.25; // seconds

function updateLyrics(currentTime) {
  currentTime += SYNC_LEAD_TIME;
  let activeEl = null;
  for (const el of wordEls) {
    const start = parseFloat(el.dataset.start);
    const end = parseFloat(el.dataset.end);
    if (currentTime >= end) {
      el.classList.remove("active");
      el.classList.add("sung");
    } else if (currentTime >= start && currentTime < end) {
      el.classList.add("active");
      el.classList.remove("sung");
      activeEl = el;
    } else {
      el.classList.remove("active", "sung");
    }
  }
  if (activeEl) {
    activeEl.scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

// ---------------------------------------------------------------------------
// Audio playback + EQ visualizer
// ---------------------------------------------------------------------------

function ensureAudioContext() {
  if (audioCtx) return;
  audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const source = audioCtx.createMediaElementSource(audio);
  analyser = audioCtx.createAnalyser();
  analyser.fftSize = 256;
  source.connect(analyser);
  analyser.connect(audioCtx.destination);
}

playBtn.addEventListener("click", async () => {
  ensureAudioContext();
  if (audioCtx.state === "suspended") {
    await audioCtx.resume();
  }
  if (audio.paused) {
    audio.play();
    playBtn.textContent = "Pause";
  } else {
    audio.pause();
    playBtn.textContent = "Play";
  }
});

// Drive lyric highlighting from requestAnimationFrame instead of the
// "timeupdate" event, which browsers throttle to ~4 updates/sec and can
// make highlighting visibly lag behind the audio.
function syncLoop() {
  requestAnimationFrame(syncLoop);
  if (audio.paused) return;
  updateLyrics(audio.currentTime);
  if (!isSeeking) updateSeekUI();
}
requestAnimationFrame(syncLoop);

audio.addEventListener("timeupdate", () => {
  if (audio.paused) {
    updateLyrics(audio.currentTime);
    if (!isSeeking) updateSeekUI();
  }
});
audio.addEventListener("ended", () => {
  playBtn.textContent = "Play";
});

function drawVisualizer() {
  requestAnimationFrame(drawVisualizer);

  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  if (!analyser) return;

  const bufferLength = analyser.frequencyBinCount;
  const data = new Uint8Array(bufferLength);
  analyser.getByteFrequencyData(data);

  const barWidth = canvas.width / bufferLength;
  for (let i = 0; i < bufferLength; i++) {
    const barHeight = (data[i] / 255) * canvas.height;
    const hue = 210 - (data[i] / 255) * 60;
    ctx.fillStyle = `hsl(${hue}, 70%, 55%)`;
    ctx.fillRect(i * barWidth, canvas.height - barHeight, barWidth - 1, barHeight);
  }
}

// ---------------------------------------------------------------------------
// Mic input + live pitch detection / scoring
// ---------------------------------------------------------------------------

async function enableMic() {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    ensureAudioContext();

    micSampleRate = audioCtx.sampleRate;
    const micSource = audioCtx.createMediaStreamSource(stream);
    micAnalyser = audioCtx.createAnalyser();
    micAnalyser.fftSize = 2048;
    micSource.connect(micAnalyser);

    micDetector = PitchDetector.forFloat32Array(micAnalyser.fftSize);
    micBuffer = new Float32Array(micAnalyser.fftSize);

    scoreHits = 0;
    scoreTotal = 0;
    scoreDisplay.classList.remove("hidden");

    micBtn.textContent = "Mic Enabled";
    micBtn.disabled = true;

    requestAnimationFrame(updatePitch);
  } catch (err) {
    pitchLabel.textContent = `Mic error: ${err.message}`;
  }
}

micBtn.addEventListener("click", enableMic);

function getReferenceFrequency(currentTime) {
  if (!referencePitch || pitchHopSeconds <= 0) return null;
  const idx = Math.round(currentTime / pitchHopSeconds);
  if (idx < 0 || idx >= referencePitch.f0.length) return null;
  if (!referencePitch.voiced[idx]) return null;
  return referencePitch.f0[idx];
}

function updatePitch() {
  requestAnimationFrame(updatePitch);
  if (!micAnalyser || !micDetector) return;

  micAnalyser.getFloatTimeDomainData(micBuffer);
  const [pitch, clarity] = micDetector.findPitch(micBuffer, micSampleRate);

  const refFreq = getReferenceFrequency(audio.currentTime);

  if (clarity < 0.9 || !refFreq) {
    pitchNeedle.className = "";
    pitchNeedle.style.left = "50%";
    pitchLabel.textContent = refFreq ? "Listening..." : "(instrumental section)";
    return;
  }

  const cents = 1200 * Math.log2(pitch / refFreq);
  const clamped = Math.max(-100, Math.min(100, cents));
  const positionPct = 50 + (clamped / 100) * 50;
  pitchNeedle.style.left = `${positionPct}%`;

  let cls, label;
  if (Math.abs(cents) <= 15) {
    cls = "in-tune";
    label = "In tune!";
  } else if (Math.abs(cents) <= 50) {
    cls = cents > 0 ? "sharp" : "flat";
    label = cents > 0 ? "Slightly sharp" : "Slightly flat";
  } else {
    cls = "far";
    label = cents > 0 ? "Sharp" : "Flat";
  }
  pitchNeedle.className = cls;
  pitchLabel.textContent = label;

  // Only score while the track is actually playing.
  if (!audio.paused) {
    scoreTotal++;
    if (Math.abs(cents) <= 50) scoreHits++;
    if (scoreTotal > 0) {
      scoreValue.textContent = Math.round((scoreHits / scoreTotal) * 100);
    }
  }
}

// ---------------------------------------------------------------------------
// Manual fine-tuning: global offset slider + "tap to sync" line retiming
// ---------------------------------------------------------------------------

syncToggleBtn.addEventListener("click", () => {
  syncPanel.classList.toggle("hidden");
});

// Live preview: shift every timed element by the slider's offset without
// touching the saved file, so you can hear/see the effect before committing.
syncOffsetSlider.addEventListener("input", () => {
  const offset = parseFloat(syncOffsetSlider.value);
  syncOffsetValue.textContent = `${offset.toFixed(2)}s`;
  for (const { el, start, end } of baseTimings) {
    el.dataset.start = start + offset;
    el.dataset.end = end + offset;
  }
  updateLyrics(audio.currentTime);
});

syncOffsetSaveBtn.addEventListener("click", async () => {
  const offset = parseFloat(syncOffsetSlider.value);
  if (offset === 0) return;
  syncOffsetSaveBtn.disabled = true;
  syncOffsetSaveBtn.textContent = "Saving...";
  try {
    const res = await fetch("/api/adjust-sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ song_id: songId, offset }),
    });
    if (!res.ok) {
      alert("Error saving offset");
      return;
    }
    // Bake the offset into the in-memory base timings and reset the slider
    // to 0 so the slider always represents "additional" adjustment.
    for (const timing of baseTimings) {
      timing.start += offset;
      timing.end += offset;
    }
    for (const seg of segmentGroups) {
      seg.start += offset;
      seg.end += offset;
    }
    syncOffsetSlider.value = "0";
    syncOffsetValue.textContent = "0.00s";
  } finally {
    syncOffsetSaveBtn.disabled = false;
    syncOffsetSaveBtn.textContent = "Save Offset";
  }
});

// Tap-to-sync: step through each lyric line, recording the audio time when
// the user taps/presses space at the moment that line should start singing.
let tapSyncActive = false;
let tapIndex = 0;
let tapStarts = [];

const DEFAULT_TAP_HINT = "Play the song, then tap (or press Space) at the start of each highlighted line.";

function highlightTapTarget(index) {
  for (const seg of segmentGroups) {
    for (const g of seg.groups) g.classList.remove("tap-target");
  }
  if (index >= 0 && index < segmentGroups.length) {
    for (const g of segmentGroups[index].groups) g.classList.add("tap-target");
    segmentGroups[index].groups[0].scrollIntoView({ block: "center", behavior: "smooth" });
  }
}

function startTapSync() {
  if (segmentGroups.length === 0) return;
  tapSyncActive = true;
  tapIndex = 0;
  tapStarts = [];
  tapSyncBtn.textContent = "Stop & Save";
  tapSyncBtn.classList.add("active");
  tapSyncHint.textContent = `Line 1 of ${segmentGroups.length}: tap (or press Space) when it starts.`;
  highlightTapTarget(0);
}

async function finishTapSync() {
  tapSyncActive = false;
  tapSyncBtn.textContent = "Start Tap Sync";
  tapSyncBtn.classList.remove("active");
  highlightTapTarget(-1);

  if (tapStarts.length === 0) {
    tapSyncHint.textContent = DEFAULT_TAP_HINT;
    return;
  }

  // Fill any untapped trailing lines with their current start times.
  const starts = segmentGroups.map((seg, i) => (i < tapStarts.length ? tapStarts[i] : seg.start));

  tapSyncHint.textContent = "Saving...";
  try {
    const res = await fetch("/api/retime-lyrics", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ song_id: songId, starts }),
    });
    if (!res.ok) {
      tapSyncHint.textContent = "Error saving. Try again.";
      return;
    }
    const timestamps = await fetch(`/library/${songId}/timestamps.json?t=${Date.now()}`).then((r) => r.json());
    renderLyrics(timestamps);
  } finally {
    tapSyncHint.textContent = DEFAULT_TAP_HINT;
  }
}

function registerTap() {
  if (!tapSyncActive) return;
  tapStarts.push(audio.currentTime);
  tapIndex++;
  if (tapIndex >= segmentGroups.length) {
    finishTapSync();
  } else {
    tapSyncHint.textContent = `Line ${tapIndex + 1} of ${segmentGroups.length}: tap (or press Space) when it starts.`;
    highlightTapTarget(tapIndex);
  }
}

tapSyncBtn.addEventListener("click", () => {
  if (tapSyncActive) {
    finishTapSync();
  } else {
    startTapSync();
  }
});

window.addEventListener("keydown", (e) => {
  if (e.code === "Space" && tapSyncActive) {
    e.preventDefault();
    registerTap();
    return;
  }
  if (e.key === "Escape") {
    // While tap-syncing, Escape backs out of that mode; otherwise it exits the
    // player back to the library (the single escape hatch).
    if (tapSyncActive) {
      e.preventDefault();
      finishTapSync();
    } else {
      window.location.href = "/";
    }
  }
});

// ---------------------------------------------------------------------------

loadData();
drawVisualizer();
