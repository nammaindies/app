import { useEffect, useState } from "react";
import { getDex, UnauthorizedError, type Sighting } from "../api";
import DogMap from "../components/DogMap";

export default function Dex({ onUnauthorized }: { onUnauthorized: () => void }) {
  const [sightings, setSightings] = useState<Sighting[] | null>(null);
  const [view, setView] = useState<"map" | "gallery">("map");
  const [selected, setSelected] = useState<Sighting | null>(null);

  useEffect(() => {
    getDex()
      .then((res) => setSightings(res.sightings))
      .catch((err) => {
        if (err instanceof UnauthorizedError) onUnauthorized();
        else setSightings([]);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (sightings === null) {
    return <div className="empty-state">Fetching your dex…</div>;
  }

  return (
    <div>
      <div className="dex-toggle">
        <button className={view === "map" ? "active" : ""} onClick={() => setView("map")}>
          Map
        </button>
        <button className={view === "gallery" ? "active" : ""} onClick={() => setView("gallery")}>
          Gallery
        </button>
      </div>

      {sightings.length === 0 ? (
        <div className="empty-state">
          <div style={{ fontSize: "2rem" }}>🐾</div>
          No sightings yet — go log your first street dog!
        </div>
      ) : view === "map" ? (
        <DogMap sightings={sightings} />
      ) : (
        <div className="gallery-grid">
          {sightings.map((s) => (
            <div key={s.id} className="gallery-card" onClick={() => setSelected(s)}>
              {s.photos[0] && <img src={s.photos[0].thumb_url} alt="dog sighting" />}
            </div>
          ))}
        </div>
      )}

      {selected && (
        <div className="viewer-overlay" onClick={() => setSelected(null)}>
          <div onClick={(e) => e.stopPropagation()}>
            {selected.photos[0] && <img src={selected.photos[0].url} alt="dog sighting" />}
            <p className="viewer-caption">{new Date(selected.captured_at).toLocaleString()}</p>
          </div>
        </div>
      )}
    </div>
  );
}
