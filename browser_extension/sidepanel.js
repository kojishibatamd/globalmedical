const topicInput = document.getElementById("topic");
const captureMode = document.getElementById("captureMode");
const outputMode = document.getElementById("outputMode");
const preview = document.getElementById("preview");
const command = document.getElementById("command");

function buildRaw(topic, meta, content) {
  return `# ${topic}

## Source
- URL: ${meta.url}
- Title: ${meta.title}
- Service: ${meta.service}
- Captured: ${new Date().toISOString()}

## Content
${content}`;
}

function buildDiscussion(topic, content) {
  return `# ${topic}

## 背景
${content}

## 現時点の論点

## 制約

## 次アクション候補`;
}

async function getData() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return chrome.tabs.sendMessage(tab.id, { type: "GET_CAPTURE" });
}

document.getElementById("captureBtn").onclick = async () => {
  const topic = topicInput.value.trim();
  if (!topic) return alert("Topic required");

  const data = await getData();
  const content = captureMode.value === "selected"
    ? data.selectedText
    : data.pageText;

  if (!content) return alert("No content");

  if (outputMode.value === "discussion") {
    preview.value = buildDiscussion(topic, content);
  } else {
    preview.value = buildRaw(topic, data, content);
  }

  command.textContent = `./scripts/ai_pipeline.sh ${topic}`;
};

document.getElementById("copyBtn").onclick = async () => {
  await navigator.clipboard.writeText(preview.value);
  alert("Copied");
};

document.getElementById("saveBtn").onclick = async () => {
  const topic = topicInput.value.trim();
  if (!topic) return alert("Topic required");

  const data = await getData();

  chrome.runtime.sendMessage({
    type: "SAVE_CAPTURE",
    topic,
    mode: outputMode.value,
    content: preview.value,
    url: data.url,
    title: data.title
  }, () => alert("Saved"));
};
