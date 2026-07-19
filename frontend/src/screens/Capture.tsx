import { useRef, useState } from "react";
import { postSighting, UnauthorizedError, type GeoSource } from "../api";
import { enqueue } from "../offline/queue";

function getLocation(): Promise<GeolocationPosition | null> {
  return new Promise((resolve) => {
    if (!("geolocation" in navigator)) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve(pos),
      () => resolve(null),
      { timeout: 8000, enableHighAccuracy: true },
    );
  });
}

export default function Capture({ onUnauthorized }: { onUnauthorized: () => void }) {
  const fileRef = useRef<HTMLInputElement>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 2600);
  }

  function onFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setPhoto(f);
    setPreviewUrl(URL.createObjectURL(f));
  }

  function reset() {
    setPhoto(null);
    setPreviewUrl(null);
    setNote("");
    if (fileRef.current) fileRef.current.value = "";
  }

  async function submit() {
    if (!photo) return;
    setSubmitting(true);
    const capturedAt = new Date().toISOString();
    const position = await getLocation();

    const geoSource: GeoSource = position ? "device_gps" : "none";
    const input = {
      photos: [photo],
      lat: position?.coords.latitude,
      lng: position?.coords.longitude,
      geo_accuracy_m: position?.coords.accuracy,
      geo_source: geoSource,
      captured_at: capturedAt,
      note: note || undefined,
    };

    try {
      await postSighting(input);
      showToast("Woof! Sighting saved 🐾");
      reset();
    } catch (err) {
      if (err instanceof UnauthorizedError) {
        onUnauthorized();
        return;
      }
      // Network failure (offline) or other error: queue for later.
      try {
        await enqueue(input);
        showToast("Saved offline — will sync later");
        reset();
      } catch {
        showToast("Couldn't save. Try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="capture-stage">
      <div className="preview-frame">
        {previewUrl ? (
          <img src={previewUrl} alt="captured dog" />
        ) : (
          <div className="placeholder">
            <div style={{ fontSize: "2.4rem" }}>🐕</div>
            <p>Spot a street dog? Snap a photo.</p>
          </div>
        )}
      </div>

      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        capture="environment"
        style={{ display: "none" }}
        onChange={onFileChosen}
      />

      {!photo ? (
        <div className="shutter-wrap">
          <button className="shutter" onClick={() => fileRef.current?.click()} aria-label="Take photo">
            📷
          </button>
          <p className="hint">Tap to open camera</p>
        </div>
      ) : (
        <>
          <div className="note-field">
            <textarea
              rows={2}
              placeholder="Add a note (optional) — e.g. friendly, limping, near the tea stall…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <div className="actions-row">
            <button className="btn btn-secondary" onClick={reset} disabled={submitting}>
              Retake
            </button>
            <button className="btn btn-primary" onClick={submit} disabled={submitting}>
              {submitting ? <span className="spinner" /> : "Log sighting"}
            </button>
          </div>
        </>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
