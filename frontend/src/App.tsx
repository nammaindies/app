import { useEffect, useState } from "react";
import Capture from "./screens/Capture";
import Dex from "./screens/Dex";
import { flush } from "./offline/queue";
import { getDex, UnauthorizedError } from "./api";

type Tab = "capture" | "dex";

export default function App() {
  const [tab, setTab] = useState<Tab>("capture");
  const [unauthorized, setUnauthorized] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    flush();
    window.addEventListener("online", flush);
    return () => window.removeEventListener("online", flush);
  }, []);

  // One-time auth probe so the invite-needed state shows immediately on
  // load, rather than only after the user tries to submit or view the dex.
  useEffect(() => {
    getDex()
      .then(() => setCheckingAuth(false))
      .catch((err) => {
        if (err instanceof UnauthorizedError) setUnauthorized(true);
        setCheckingAuth(false);
      });
  }, []);

  if (checkingAuth) {
    return <div className="app" />;
  }

  if (unauthorized) {
    return (
      <div className="app">
        <div className="screen gate">
          <div className="big-paw">🐕‍🦺</div>
          <h2>You need an invite</h2>
          <p className="hint">
            Namma IndieDex is invite-only right now. Ask a friend for a magic link, or
            check your email for one, to start logging sightings.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <div className="topbar">
        <span className="brand">
          <span className="pawmark">🐾</span> Namma IndieDex
        </span>
      </div>
      <div className="screen">
        {tab === "capture" ? (
          <Capture onUnauthorized={() => setUnauthorized(true)} />
        ) : (
          <Dex onUnauthorized={() => setUnauthorized(true)} />
        )}
      </div>
      <div className="tabbar">
        <button className={tab === "capture" ? "active" : ""} onClick={() => setTab("capture")}>
          <span className="icon">📷</span>
          Capture
        </button>
        <button className={tab === "dex" ? "active" : ""} onClick={() => setTab("dex")}>
          <span className="icon">🗺️</span>
          IndieDex
        </button>
      </div>
    </div>
  );
}
