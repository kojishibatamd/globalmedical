function detectService() {
  const host = location.host.toLowerCase();
  if (host.includes("chatgpt")) return "chatgpt";
  if (host.includes("claude")) return "claude";
  if (host.includes("github")) return "github";
  return "generic";
}

function getSelectedText() {
  return window.getSelection()?.toString() || "";
}

function getPageText() {
  return document.body?.innerText || "";
}

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "GET_CAPTURE") {
    sendResponse({
      url: location.href,
      title: document.title,
      service: detectService(),
      selectedText: getSelectedText(),
      pageText: getPageText()
    });
  }
});
