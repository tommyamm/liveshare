const editor = document.getElementById("editor");
const wsStatus = document.getElementById("ws-status");
const bridgeStatus = document.getElementById("bridge-status");
const participants = document.getElementById("participants");
const saveState = document.getElementById("save-state");
const lineCount = document.getElementById("line-count");

const BRIDGE_URL = "http://127.0.0.1:8765";
const DEBOUNCE_MS = 75;

let socket = null;
let debounceTimer = null;
let bridgeOnline = false;
let applyingRemote = false;
let lastSyncedContent = "";

function setStatus(element, value, online) {
  element.textContent = value;
  element.classList.toggle("online", online);
  element.classList.toggle("offline", !online);
}

function updateLineCount() {
  const lines = editor.value.split("\n").length;
  lineCount.textContent = `${lines} ${lines === 1 ? "line" : "lines"}`;
}

async function saveToBridge(content) {
  try {
    const response = await fetch(`${BRIDGE_URL}/file`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });

    if (!response.ok) {
      throw new Error("bridge write failed");
    }

    bridgeOnline = true;
    setStatus(bridgeStatus, "online", true);
    return true;
  } catch (error) {
    bridgeOnline = false;
    setStatus(bridgeStatus, "offline", false);
    saveState.textContent = "Local file bridge is unavailable";
    return false;
  }
}

async function loadFromBridge() {
  try {
    const response = await fetch(`${BRIDGE_URL}/file`);
    if (!response.ok) {
      throw new Error("bridge read failed");
    }

    const payload = await response.json();
    if (typeof payload.content === "string" && !editor.value) {
      editor.value = payload.content;
      lastSyncedContent = payload.content;
      updateLineCount();
    }

    bridgeOnline = true;
    setStatus(bridgeStatus, "online", true);
  } catch (error) {
    bridgeOnline = false;
    setStatus(bridgeStatus, "offline", false);
    saveState.textContent = "Start sync_client.py on this machine";
  }
}

async function pushCurrentContent() {
  if (!socket || socket.readyState !== WebSocket.OPEN) {
    saveState.textContent = "Waiting for sync server";
    return;
  }

  const content = editor.value;
  lastSyncedContent = content;
  socket.send(JSON.stringify({ type: "sync", content }));
  const bridgeSaved = await saveToBridge(content);
  saveState.textContent = bridgeSaved ? "Synced just now" : "Sent to room only";
}

function schedulePush() {
  window.clearTimeout(debounceTimer);
  debounceTimer = window.setTimeout(() => {
    void pushCurrentContent();
  }, DEBOUNCE_MS);
}

function applyRemoteContent(content) {
  if (content === editor.value) {
    return;
  }

  const selectionStart = editor.selectionStart;
  const selectionEnd = editor.selectionEnd;
  const wasFocused = document.activeElement === editor;

  applyingRemote = true;
  editor.value = content;
  lastSyncedContent = content;
  updateLineCount();
  saveState.textContent = "Remote update applied";

  if (wasFocused) {
    const caret = Math.min(selectionStart, editor.value.length);
    const caretEnd = Math.min(selectionEnd, editor.value.length);
    editor.setSelectionRange(caret, caretEnd);
  }

  applyingRemote = false;
  void saveToBridge(content);
}

function connectSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socketUrl = `${protocol}//${window.location.hostname}:5678`;
  socket = new WebSocket(socketUrl);

  socket.addEventListener("open", () => {
    setStatus(wsStatus, "online", true);
    saveState.textContent = "Connected";
  });

  socket.addEventListener("close", () => {
    setStatus(wsStatus, "offline", false);
    saveState.textContent = "Reconnect in 1 second";
    window.setTimeout(connectSocket, 1000);
  });

  socket.addEventListener("message", (event) => {
    const payload = JSON.parse(event.data);

    if (payload.type === "presence") {
      participants.textContent = String(payload.participants ?? 1);
      return;
    }

    if (payload.type === "sync") {
      participants.textContent = String(payload.participants ?? 1);
      if (typeof payload.content === "string") {
        applyRemoteContent(payload.content);
      }
    }
  });
}

editor.addEventListener("input", () => {
  updateLineCount();
  if (applyingRemote) {
    return;
  }
  saveState.textContent = "Typing...";
  schedulePush();
});

window.addEventListener("beforeunload", () => {
  if (editor.value !== lastSyncedContent) {
    navigator.sendBeacon?.(
      `${BRIDGE_URL}/file`,
      new Blob([JSON.stringify({ content: editor.value })], {
        type: "application/json",
      })
    );
  }
});

updateLineCount();
void loadFromBridge();
connectSocket();
