function visibleTextFromPage() {
  const selectors = [
    '[data-testid*="transcript"]',
    '[class*="transcript"]',
    '[class*="minutes"]',
    '[class*="record"]',
    'main',
    'article',
    'body'
  ];
  for (const selector of selectors) {
    const node = document.querySelector(selector);
    if (node && node.innerText && node.innerText.trim().length > 300) {
      return node.innerText.trim();
    }
  }
  return document.body.innerText.trim();
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.type === "EXTRACT_TRANSCRIPT") {
    sendResponse({
      title: document.title || "",
      transcript: visibleTextFromPage()
    });
  }
  return true;
});
