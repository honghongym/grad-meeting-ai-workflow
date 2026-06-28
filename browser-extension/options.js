const apiBase = document.getElementById("apiBase");
const apiToken = document.getElementById("apiToken");
const status = document.getElementById("status");

chrome.storage.sync.get({ apiBase: "http://localhost:8000", apiToken: "" }, (items) => {
  apiBase.value = items.apiBase;
  apiToken.value = items.apiToken;
});

document.getElementById("save").addEventListener("click", () => {
  chrome.storage.sync.set(
    {
      apiBase: apiBase.value.replace(/\/$/, ""),
      apiToken: apiToken.value
    },
    () => {
      status.textContent = "已保存";
      setTimeout(() => (status.textContent = ""), 1800);
    }
  );
});
