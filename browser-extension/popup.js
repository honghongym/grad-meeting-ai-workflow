const fields = {
  meetingType: document.getElementById("meetingType"),
  topic: document.getElementById("topic"),
  attendees: document.getElementById("attendees"),
  transcript: document.getElementById("transcript"),
  status: document.getElementById("status"),
  error: document.getElementById("error"),
  bar: document.getElementById("bar"),
  result: document.getElementById("result"),
  resultText: document.getElementById("resultText")
};

let currentMeetingId = null;
let currentApiBase = "http://localhost:8000";
let currentApiToken = "";

function today() {
  return new Date().toISOString().slice(0, 10);
}

function headers() {
  const h = { "Content-Type": "application/json" };
  if (currentApiToken) h["X-API-Token"] = currentApiToken;
  return h;
}

function setStatus(text) {
  fields.status.textContent = text;
}

function setError(text) {
  fields.error.textContent = text || "";
}

function api(path, options = {}) {
  return fetch(`${currentApiBase}${path}`, {
    ...options,
    headers: { ...headers(), ...(options.headers || {}) }
  });
}

chrome.storage.sync.get({ apiBase: "http://localhost:8000", apiToken: "" }, (items) => {
  currentApiBase = items.apiBase.replace(/\/$/, "");
  currentApiToken = items.apiToken;
});

document.getElementById("extract").addEventListener("click", async () => {
  setError("");
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  chrome.tabs.sendMessage(tab.id, { type: "EXTRACT_TRANSCRIPT" }, (response) => {
    if (chrome.runtime.lastError || !response) {
      setError("无法读取当前页面，请刷新页面或手动粘贴转写文本。");
      return;
    }
    fields.topic.value = fields.topic.value || response.title || "未命名会议";
    fields.transcript.value = response.transcript || "";
    setStatus(`已提取 ${fields.transcript.value.length} 字`);
  });
});

document.getElementById("submit").addEventListener("click", async () => {
  setError("");
  fields.result.hidden = true;
  const payload = {
    meeting_date: today(),
    meeting_type: fields.meetingType.value,
    topic: fields.topic.value || "未命名会议",
    attendees: fields.attendees.value.split(/[,，]/).map((x) => x.trim()).filter(Boolean),
    transcript: fields.transcript.value
  };
  if (!payload.transcript || payload.transcript.length < 20) {
    setError("请先提取或粘贴会议转写文本。");
    return;
  }
  try {
    setStatus("已提交，等待后端处理...");
    const response = await api("/api/meetings", {
      method: "POST",
      body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    currentMeetingId = data.meeting_id;
    pollProgress();
  } catch (error) {
    setError(`提交失败：${error.message}`);
  }
});

async function pollProgress() {
  if (!currentMeetingId) return;
  try {
    const response = await api(`/api/meetings/${currentMeetingId}/progress`);
    const progress = await response.json();
    fields.bar.style.width = `${progress.percent}%`;
    setStatus(progress.label);
    if (progress.is_running) {
      setTimeout(pollProgress, 1500);
    } else {
      loadResult();
    }
  } catch (error) {
    setError(`进度读取失败：${error.message}`);
  }
}

async function loadResult() {
  const response = await api(`/api/meetings/${currentMeetingId}/result`);
  const data = await response.json();
  fields.result.hidden = false;
  fields.resultText.textContent = data.status === "draft_ready"
    ? "纪要草稿已生成，可以打开详情页审阅。"
    : `当前状态：${data.status}`;
}

document.getElementById("openDetail").addEventListener("click", () => {
  if (currentMeetingId) chrome.tabs.create({ url: `${currentApiBase}/meetings/${currentMeetingId}` });
});

document.getElementById("copyMarkdown").addEventListener("click", async () => {
  if (!currentMeetingId) return;
  const response = await api(`/api/meetings/${currentMeetingId}/markdown`);
  const markdown = await response.text();
  await navigator.clipboard.writeText(markdown);
  setStatus("Markdown 已复制");
});
