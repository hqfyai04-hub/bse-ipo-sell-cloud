let deferredInstallPrompt = null;
const installButton = document.getElementById("installAppBtn");

function isNativeApp() {
  return Boolean(window.Capacitor?.isNativePlatform?.() || window.APP_CONFIG?.NATIVE_BUILD);
}

function hideInstallButton() {
  if (installButton) installButton.hidden = true;
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  if (installButton && !isNativeApp()) installButton.hidden = false;
});

installButton?.addEventListener("click", async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  await deferredInstallPrompt.userChoice;
  deferredInstallPrompt = null;
  hideInstallButton();
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  hideInstallButton();
});

if (window.matchMedia("(display-mode: standalone)").matches || isNativeApp()) {
  document.documentElement.classList.add("installed-app");
  hideInstallButton();
}

if ("serviceWorker" in navigator && !isNativeApp()) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/service-worker.js", { scope: "/" }).catch(() => {
      // 安装失败不影响实时判断；Chrome 开发者工具会显示具体原因。
    });
  });
}
