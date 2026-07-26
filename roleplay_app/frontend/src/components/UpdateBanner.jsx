import { useEffect, useState } from "react";

export default function UpdateBanner() {
  const [updateReady, setUpdateReady] = useState(false);

  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    // Only a *replacement* of an already-active worker means a real update - the very first
    // controllerchange on a fresh install doesn't count.
    const hadController = !!navigator.serviceWorker.controller;
    const onControllerChange = () => {
      if (hadController) setUpdateReady(true);
    };
    navigator.serviceWorker.addEventListener("controllerchange", onControllerChange);

    // Installed PWAs have no address bar/reload button and don't reliably poll for updates
    // in the background, so ask explicitly whenever the app is foregrounded.
    const checkForUpdate = () => {
      if (document.visibilityState === "visible") {
        navigator.serviceWorker.getRegistration().then((reg) => reg?.update());
      }
    };
    document.addEventListener("visibilitychange", checkForUpdate);
    checkForUpdate();

    return () => {
      navigator.serviceWorker.removeEventListener("controllerchange", onControllerChange);
      document.removeEventListener("visibilitychange", checkForUpdate);
    };
  }, []);

  if (!updateReady) return null;

  return (
    <div className="update-banner">
      <span>A new version is available.</span>
      <button onClick={() => window.location.reload()}>Refresh</button>
    </div>
  );
}
