import { useRef, useState } from "react";
import {
  postSighting,
  UnauthorizedError,
  type Condition,
  type EarNotch,
  type GeoSource,
  type Sex,
} from "../api";
import { enqueue } from "../offline/queue";

const SEX_OPTIONS: { value: Sex; label: string }[] = [
  { value: "male", label: "♂ male" },
  { value: "female", label: "♀ female" },
  { value: "unsure", label: "unsure" },
];

const EAR_NOTCH_OPTIONS: { value: EarNotch; label: string }[] = [
  { value: "none", label: "none" },
  { value: "left", label: "left" },
  { value: "right", label: "right" },
  { value: "unsure", label: "unsure" },
];

const CONDITION_OPTIONS: { value: Condition; label: string }[] = [
  { value: "healthy", label: "healthy" },
  { value: "injured", label: "injured" },
  { value: "unsure", label: "unsure" },
];

function Chips<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T | null;
  onChange: (v: T | null) => void;
}) {
  return (
    <div className="chip-row">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={"chip" + (value === o.value ? " active" : "")}
          onClick={() => onChange(value === o.value ? null : o.value)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

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
  const videoRef = useRef<HTMLInputElement>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const [video, setVideo] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [sex, setSex] = useState<Sex | null>(null);
  const [earNotch, setEarNotch] = useState<EarNotch | null>(null);
  const [condition, setCondition] = useState<Condition | null>(null);
  const [moreOpen, setMoreOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  function showToast(msg: string) {
    setToast(msg);
    setTimeout(() => setToast(null), 2600);
  }

  function onFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setVideo(null);
    setPhoto(f);
    setPreviewUrl(URL.createObjectURL(f));
  }

  function onVideoChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0];
    if (!f) return;
    setPhoto(null);
    setVideo(f);
    setPreviewUrl(URL.createObjectURL(f));
  }

  function reset() {
    setPhoto(null);
    setVideo(null);
    setPreviewUrl(null);
    setNote("");
    setSex(null);
    setEarNotch(null);
    setCondition(null);
    setMoreOpen(false);
    if (fileRef.current) fileRef.current.value = "";
    if (videoRef.current) videoRef.current.value = "";
  }

  async function submit() {
    if (!photo && !video) return;
    setSubmitting(true);
    const capturedAt = new Date().toISOString();
    const position = await getLocation();

    const geoSource: GeoSource = position ? "device_gps" : "none";
    const input = {
      photos: photo ? [photo] : undefined,
      video: video ?? undefined,
      lat: position?.coords.latitude,
      lng: position?.coords.longitude,
      geo_accuracy_m: position?.coords.accuracy,
      geo_source: geoSource,
      captured_at: capturedAt,
      note: note || undefined,
      sex: sex || undefined,
      ear_notch: earNotch || undefined,
      condition: condition || undefined,
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
        {previewUrl && video ? (
          <video src={previewUrl} controls muted />
        ) : previewUrl ? (
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
      <input
        ref={videoRef}
        type="file"
        accept="video/*"
        capture="environment"
        style={{ display: "none" }}
        onChange={onVideoChosen}
      />

      {!photo && !video ? (
        <div className="shutter-wrap">
          <button className="shutter" onClick={() => fileRef.current?.click()} aria-label="Take photo">
            📷
          </button>
          <p className="hint">Tap to open camera</p>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => videoRef.current?.click()}
          >
            🎥 Record video
          </button>
          <p className="hint">Record a few seconds → we keep the best frames.</p>
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

          <button
            type="button"
            className="more-toggle"
            onClick={() => setMoreOpen((v) => !v)}
          >
            {moreOpen ? "▾" : "▸"} tell us more (optional)
          </button>

          {moreOpen && (
            <div className="more-fields">
              <div className="field-group">
                <label>sex</label>
                <Chips options={SEX_OPTIONS} value={sex} onChange={setSex} />
              </div>
              <div className="field-group">
                <label>ear-notch (sterilized?)</label>
                <Chips options={EAR_NOTCH_OPTIONS} value={earNotch} onChange={setEarNotch} />
              </div>
              <div className="field-group">
                <label>condition</label>
                <Chips options={CONDITION_OPTIONS} value={condition} onChange={setCondition} />
              </div>
            </div>
          )}

          <div className="actions-row">
            <button className="btn btn-secondary" onClick={reset} disabled={submitting}>
              Retake
            </button>
            <button className="btn btn-primary" onClick={submit} disabled={submitting}>
              {submitting ? (
                <span className="spinner" />
              ) : (
                "Log sighting"
              )}
            </button>
            {submitting && video && <p className="hint">Extracting frames from your clip…</p>}
          </div>
        </>
      )}

      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}
