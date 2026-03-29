chrome.runtime.onInstalled.addListener(() => {
  console.log("Extension installed");
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "SAVE_CAPTURE") {
    chrome.storage.local.get(["captures"], (result) => {
      const captures = result.captures || [];
      captures.push({
        topic: message.topic,
        mode: message.mode,
        content: message.content,
        url: message.url,
        title: message.title,
        createdAt: new Date().toISOString()
      });
      chrome.storage.local.set({ captures }, () => {
        sendResponse({ ok: true });
      });
    });
    return true;
  }
});
