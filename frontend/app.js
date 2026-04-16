/**
 * K — Voice Assistant
 * State machine: IDLE → LISTENING → PROCESSING → SPEAKING → IDLE
 *
 * Silence detection: 2 seconds of no new speech → auto-submit
 * Voice: emotional TTS — pitch/rate vary by sentiment
 * Subtitles: karaoke-style word-boundary tracking
 */

// ── Elements ──────────────────────────────────────────────────────────────
const micBtn         = document.getElementById("mic-btn");
const catSvg         = document.getElementById("cat");
const glowEl         = document.getElementById("glow");
const mouthShape     = document.getElementById("mouth-shape");
const mouthBg        = document.getElementById("mouth-bg");
const mouthCurve     = document.getElementById("mouth-curve");
const statusLabel    = document.getElementById("status-label");
const hintLabel      = document.getElementById("hint-label");
const transcriptEl   = document.getElementById("transcript");
const replyEl        = document.getElementById("reply");
const authBanner     = document.getElementById("auth-banner");
const agendaList     = document.getElementById("agenda-list");
const historyList    = document.getElementById("history-list");
const userEmailEl    = document.getElementById("user-email");
const btnLogout      = document.getElementById("btn-logout");
const toastContainer = document.getElementById("toast-container");
const subtitleBar    = document.getElementById("subtitle-bar");
const waveBars       = document.getElementById("wave-bars");

// ── State ─────────────────────────────────────────────────────────────────
const STATES = { IDLE: "idle", LISTENING: "listening", PROCESSING: "processing", SPEAKING: "speaking" };
let appState          = STATES.IDLE;
let recognition       = null;
let pendingTranscript = "";
let silenceTimer      = null;
let mouthAnimId       = null;
let selectedVoice     = null;
let subtitleHideTimer = null;
let subtitleWordTimer = null;
let boundaryFired     = false;

const SILENCE_MS        = 2000;
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const synth             = window.speechSynthesis;

// ── Voice selection ────────────────────────────────────────────────────────
// Priority: premium neural → Google neural → macOS premium → any en-US
const VOICE_PRIORITY = [
  "Samantha (Premium)",        // macOS 13+ neural — most human-sounding
  "Karen (Premium)",
  "Matilda (Premium)",
  "Microsoft Aria Online (Natural) - English (United States)",  // Edge neural
  "Microsoft Jenny Online (Natural) - English (United States)",
  "Microsoft Sonia Online (Natural) - English (United Kingdom)",
  "Google US English",         // Chrome neural
  "Google UK English Female",
  "Samantha",
  "Karen",
  "Moira",
  "Tessa",
  "Serena",
];

function pickBestVoice() {
  const voices = synth.getVoices();
  if (!voices.length) return null;
  for (const name of VOICE_PRIORITY) {
    const v = voices.find(v => v.name === name);
    if (v) return v;
  }
  return voices.find(v => v.lang.startsWith("en-US")) || voices[0] || null;
}

if (synth.onvoiceschanged !== undefined) {
  synth.onvoiceschanged = () => { selectedVoice = pickBestVoice(); };
}
selectedVoice = pickBestVoice();

// ── Boot ──────────────────────────────────────────────────────────────────
if (!SpeechRecognition) {
  showUnsupported();
} else {
  handleAuthRedirect();
  checkAuth();
}

// ── Mic: press-and-hold (mouse + touch) ───────────────────────────────────
micBtn.addEventListener("mousedown",  onMicDown);
micBtn.addEventListener("touchstart", onMicDown, { passive: true });
micBtn.addEventListener("mouseup",    onMicUp);
micBtn.addEventListener("touchend",   onMicUp);
micBtn.addEventListener("mouseleave", onMicUp);

micBtn.addEventListener("keydown", (e) => {
  if (e.key === " " || e.key === "Enter") {
    e.preventDefault();
    if (appState === STATES.IDLE) onMicDown();
  }
});
micBtn.addEventListener("keyup", (e) => {
  if ((e.key === " " || e.key === "Enter") && appState === STATES.LISTENING) onMicUp();
});

function onMicDown() {
  if (appState === STATES.SPEAKING) {
    synth.cancel();
    stopMouthAnim();
    hideSubtitle();
    if (waveBars) waveBars.classList.remove("active");
    setState(STATES.IDLE);
    return;
  }
  if (appState === STATES.IDLE) startListening();
}

function onMicUp() {
  // Silence timer handles submission — no action needed on release
}

// ── State machine ──────────────────────────────────────────────────────────
function setState(next) {
  appState = next;

  catSvg.className = `cat-svg ${next}`;
  glowEl.className = `glow ${next}`;
  micBtn.className = `mic-btn ${next}`;
  micBtn.setAttribute("aria-pressed", next === STATES.LISTENING ? "true" : "false");

  const labels = {
    [STATES.IDLE]:       "Hold to speak",
    [STATES.LISTENING]:  "Listening… (speak now)",
    [STATES.PROCESSING]: "Thinking…",
    [STATES.SPEAKING]:   "Speaking…",
  };
  const hints = {
    [STATES.IDLE]:       `or press <kbd>Space</kbd>`,
    [STATES.LISTENING]:  "Will process after 2 s of silence",
    [STATES.PROCESSING]: "",
    [STATES.SPEAKING]:   "Tap to interrupt",
  };

  statusLabel.textContent = labels[next] ?? "";
  hintLabel.innerHTML     = hints[next] ?? "";
}

// ── SVG Mouth animation ───────────────────────────────────────────────────
function setMouthRy(ry) {
  const r = Math.max(0, Math.round(ry));
  if (mouthShape) mouthShape.setAttribute("ry", r);
  if (mouthBg)    mouthBg.setAttribute("ry", r);
  if (mouthCurve) mouthCurve.style.opacity = r < 3 ? "1" : "0";
}

function startMouthAnim() {
  stopMouthAnim();
  let t = 0;
  function frame() {
    t += 0.2;
    setMouthRy(1 + Math.abs(Math.sin(t)) * 13);
    mouthAnimId = requestAnimationFrame(frame);
  }
  mouthAnimId = requestAnimationFrame(frame);
}

function stopMouthAnim() {
  if (mouthAnimId) {
    cancelAnimationFrame(mouthAnimId);
    mouthAnimId = null;
  }
  setMouthRy(0);
}

// ── Subtitle helpers — word-by-word floating pill ─────────────────────────
function showSubtitleWord(word) {
  if (!subtitleBar || !word.trim()) return;
  clearTimeout(subtitleHideTimer);
  subtitleBar.textContent = word.trim();
  subtitleBar.classList.add("active");
}

function showSubtitleKaraoke(fullText, charIndex, charLength) {
  showSubtitleWord(fullText.substring(charIndex, charIndex + charLength));
}

// Fallback: cycle words on a timer when onboundary never fires
function startSubtitleFallback(text) {
  clearInterval(subtitleWordTimer);
  const words = text.split(/\s+/).filter(w => w);
  let i = 0;
  function next() {
    if (i >= words.length) { clearInterval(subtitleWordTimer); return; }
    showSubtitleWord(words[i++]);
  }
  next();
  subtitleWordTimer = setInterval(next, 310);
}

function stopSubtitleFallback() {
  clearInterval(subtitleWordTimer);
  subtitleWordTimer = null;
}

function hideSubtitle(delay = 0) {
  stopSubtitleFallback();
  clearTimeout(subtitleHideTimer);
  if (delay > 0) {
    subtitleHideTimer = setTimeout(() => {
      if (subtitleBar) subtitleBar.classList.remove("active");
    }, delay);
  } else {
    if (subtitleBar) subtitleBar.classList.remove("active");
  }
}

// ── Silence timer helpers ─────────────────────────────────────────────────
function resetSilenceTimer() {
  clearTimeout(silenceTimer);
  silenceTimer = setTimeout(() => {
    if (appState === STATES.LISTENING) {
      const text = pendingTranscript.trim();
      if (text) {
        if (recognition) recognition.abort();
        sendCommand(text);
      } else {
        if (recognition) recognition.abort();
        setState(STATES.IDLE);
      }
    }
  }, SILENCE_MS);
}

function clearSilenceTimer() {
  clearTimeout(silenceTimer);
  silenceTimer = null;
}

// ── Listening ──────────────────────────────────────────────────────────────
function startListening() {
  if (!SpeechRecognition) return;

  recognition                  = new SpeechRecognition();
  recognition.lang             = "en-US";
  recognition.interimResults   = true;
  recognition.maxAlternatives  = 1;
  recognition.continuous       = true;

  transcriptEl.textContent = "";
  replyEl.textContent      = "";
  pendingTranscript        = "";

  recognition.onresult = (event) => {
    let allFinal   = "";
    let allInterim = "";
    for (const result of event.results) {
      if (result.isFinal) allFinal   += result[0].transcript + " ";
      else                allInterim += result[0].transcript;
    }
    pendingTranscript        = allFinal.trim();
    transcriptEl.textContent = pendingTranscript || allInterim;
    resetSilenceTimer();
  };

  recognition.onerror = (event) => {
    clearSilenceTimer();
    if (event.error === "no-speech" || event.error === "aborted") return;
    showToast(`Mic error: ${event.error}`, "error");
    setState(STATES.IDLE);
  };

  recognition.onend = () => {
    if (appState === STATES.LISTENING) {
      clearSilenceTimer();
      const text = pendingTranscript.trim();
      if (text) sendCommand(text);
      else      setState(STATES.IDLE);
    }
  };

  recognition.start();
  setState(STATES.LISTENING);
  resetSilenceTimer();
}

// ── Backend call ───────────────────────────────────────────────────────────
async function sendCommand(transcript) {
  clearSilenceTimer();
  setState(STATES.PROCESSING);

  try {
    const res = await fetch("/command", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ transcript }),
    });

    if (res.status === 401) {
      authBanner.hidden = false;
      speak("Please connect your Google account first.");
      return;
    }

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail ?? `Server error ${res.status}`);
    }

    const data = await res.json();
    addHistory(transcript, data.reply);
    speak(data.reply);
    if (data.action_taken) loadTodayAgenda();

  } catch (err) {
    showToast(err.message, "error");
    setState(STATES.IDLE);
  }
}

// ── Emotion analysis ───────────────────────────────────────────────────────
// Returns TTS params tuned to the emotional content of the text.
function analyzeEmotion(text) {
  const t = text.toLowerCase();

  // Excited / very positive
  if (/!/.test(text) && /great|perfect|done|created|added|set up|fantastic|wonderful|excellent|amazing|sure/i.test(t)) {
    return { rate: 1.04, pitch: 1.1, volume: 1.0 };
  }

  // Question / curious
  if (/\?/.test(text)) {
    return { rate: 0.93, pitch: 1.06, volume: 0.98 };
  }

  // Apologetic / bad news
  if (/sorry|unfortunately|can't|cannot|unable|failed|error|couldn't|not able/i.test(t)) {
    return { rate: 0.88, pitch: 0.93, volume: 0.95 };
  }

  // Confirmation / action done
  if (/done|created|scheduled|added|booked|sent|updated|deleted|removed/i.test(t)) {
    return { rate: 0.97, pitch: 1.04, volume: 1.0 };
  }

  // Greeting
  if (/^(hi|hello|hey|good morning|good evening|welcome)/i.test(t)) {
    return { rate: 0.96, pitch: 1.07, volume: 1.0 };
  }

  // Default — warm, measured, natural pacing
  return { rate: 0.88, pitch: 1.02, volume: 1.0 };
}

// ── TTS — emotional + subtitle-synced ─────────────────────────────────────
function speak(text) {
  if (!synth || !text) {
    replyEl.textContent = text || "";
    setState(STATES.IDLE);
    return;
  }

  synth.cancel();
  stopMouthAnim();
  hideSubtitle();

  if (!selectedVoice) selectedVoice = pickBestVoice();

  const emotion = analyzeEmotion(text);
  const utt     = new SpeechSynthesisUtterance(text);
  if (selectedVoice) utt.voice = selectedVoice;
  utt.rate   = emotion.rate;
  utt.pitch  = emotion.pitch;
  utt.volume = emotion.volume;

  // Word-by-word subtitle via onboundary; fallback timer if browser doesn't support it
  boundaryFired = false;

  utt.onboundary = (event) => {
    if (event.name === "word") {
      if (!boundaryFired) {
        boundaryFired = true;
        stopSubtitleFallback();  // native events working — cancel fallback
      }
      showSubtitleKaraoke(text, event.charIndex, event.charLength || 0);
    }
  };

  utt.onstart = () => {
    replyEl.textContent = text;
    setState(STATES.SPEAKING);
    startMouthAnim();
    if (waveBars) waveBars.classList.add("active");
    // Give native onboundary 400 ms; if it doesn't fire, cycle words manually
    setTimeout(() => { if (!boundaryFired) startSubtitleFallback(text); }, 400);
  };

  utt.onend = () => {
    stopMouthAnim();
    setState(STATES.IDLE);
    hideSubtitle(700);
    if (waveBars) waveBars.classList.remove("active");
  };

  utt.onerror = () => {
    stopMouthAnim();
    setState(STATES.IDLE);
    hideSubtitle();
    if (waveBars) waveBars.classList.remove("active");
  };

  synth.speak(utt);
}

// ── Agenda ─────────────────────────────────────────────────────────────────
async function loadTodayAgenda() {
  try {
    const res = await fetch("/events/today");
    if (!res.ok) { agendaList.innerHTML = `<li class="list-placeholder">Not connected</li>`; return; }
    const data = await res.json();

    if (!data.events || data.events.length === 0) {
      agendaList.innerHTML = `<li class="list-placeholder">No events today</li>`;
      return;
    }

    agendaList.innerHTML = data.events.map((ev) => {
      const time = formatEventTime(ev.start);
      const att  = ev.attendees.length
        ? ev.attendees.slice(0, 2).join(", ") + (ev.attendees.length > 2 ? ` +${ev.attendees.length - 2}` : "")
        : "";
      return `<li class="agenda-item">
        <span class="agenda-time">${time}</span>
        <span class="agenda-title">${escHtml(ev.title)}</span>
        ${att ? `<span class="agenda-attendees">${escHtml(att)}</span>` : ""}
      </li>`;
    }).join("");
  } catch {
    agendaList.innerHTML = `<li class="list-placeholder">Could not load</li>`;
  }
}

function formatEventTime(iso) {
  if (!iso) return "";
  try { return new Date(iso).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }); }
  catch { return iso; }
}

// ── History ────────────────────────────────────────────────────────────────
function addHistory(you, k) {
  const item = document.createElement("li");
  item.className = "history-item";
  item.innerHTML = `
    <div class="history-you">${escHtml(truncate(you, 80))}</div>
    <div class="history-k">${escHtml(truncate(k, 120))}</div>
  `;
  historyList.prepend(item);
  while (historyList.children.length > 10) historyList.removeChild(historyList.lastChild);
}

// ── Auth ───────────────────────────────────────────────────────────────────
function handleAuthRedirect() {
  const params = new URLSearchParams(window.location.search);
  const result = params.get("auth");
  if (result === "success") speak("Google account connected. You're all set!");
  else if (result === "error") showToast(`Google sign-in failed: ${params.get("reason") ?? "unknown"}`, "error");
  if (result) window.history.replaceState({}, "", window.location.pathname);
}

async function checkAuth() {
  try {
    const res  = await fetch("/auth/status");
    const data = await res.json();
    if (data.authenticated) {
      authBanner.hidden = true;
      btnLogout.hidden  = false;
      if (data.email) userEmailEl.textContent = data.email;
      loadTodayAgenda();
    } else {
      authBanner.hidden = false;
      agendaList.innerHTML = `<li class="list-placeholder">Sign in to see events</li>`;
    }
  } catch { /* backend not ready yet */ }
}

btnLogout.addEventListener("click", async () => {
  await fetch("/auth/logout", { method: "POST" });
  userEmailEl.textContent  = "";
  btnLogout.hidden          = true;
  authBanner.hidden         = false;
  agendaList.innerHTML      = `<li class="list-placeholder">Sign in to see events</li>`;
  historyList.innerHTML     = "";
  replyEl.textContent       = "";
  transcriptEl.textContent  = "";
});

// ── Toast ──────────────────────────────────────────────────────────────────
function showToast(message, type = "info") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${escHtml(message)}</span><button class="toast-close" aria-label="Dismiss">✕</button>`;
  toast.querySelector(".toast-close").addEventListener("click", () => toast.remove());
  toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 6000);
}

// ── Unsupported browser ────────────────────────────────────────────────────
function showUnsupported() {
  micBtn.disabled         = true;
  statusLabel.textContent = "Chrome or Edge required";
  hintLabel.textContent   = "Web Speech API not available in this browser";
}

// ── Utils ──────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;")
    .replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}
function truncate(str, n) {
  return str.length > n ? str.slice(0, n - 1) + "…" : str;
}
