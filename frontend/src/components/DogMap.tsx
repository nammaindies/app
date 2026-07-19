import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { Sighting } from "../api";

const BANGALORE: [number, number] = [77.59, 12.97];

// NOTE: OSM raster tiles are a placeholder basemap only, not licensed for
// production traffic. Swap for a proper tile provider before shipping
// beyond this MVP — tracked in GitHub issue #2.
const OSM_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [{ id: "osm", type: "raster", source: "osm" }],
};

export default function DogMap({ sightings }: { sightings: Sighting[] }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const geoed = sightings.filter((s) => s.lat != null && s.lng != null);
    const center: [number, number] =
      geoed.length > 0 ? [geoed[0].lng as number, geoed[0].lat as number] : BANGALORE;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center,
      zoom: geoed.length > 0 ? 12 : 11,
    });
    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const markers: maplibregl.Marker[] = [];
    const addMarkers = () => {
      for (const s of sightings) {
        if (s.lat == null || s.lng == null) continue;
        const thumb = s.photos[0]?.thumb_url;

        const el = document.createElement("div");
        el.className = "photo-pin";
        if (thumb) {
          const img = document.createElement("img");
          img.src = thumb;
          img.alt = "dog sighting";
          el.appendChild(img);
        } else {
          el.textContent = "🐾";
          el.classList.add("photo-pin-fallback");
        }

        const time = new Date(s.captured_at).toLocaleString();
        const attrs = s.attrs || {};
        const tagLabels: Record<string, string> = {
          male: "♂ male",
          female: "♀ female",
          left: "notched-left",
          right: "notched-right",
          healthy: "healthy",
          injured: "injured",
        };
        const rawTags = [attrs.sex, attrs.ear_notch, attrs.condition] as (
          | string
          | undefined
        )[];
        const tags = rawTags
          .filter((v): v is string => !!v && v !== "unsure" && v !== "none")
          .map((v) => tagLabels[v] ?? v);
        const popupHtml = `
          <div class="map-popup">
            ${thumb ? `<img src="${thumb}" alt="dog sighting" />` : ""}
            <div class="time">${time}</div>
            ${
              attrs.note
                ? `<div class="popup-note">${attrs.note.replace(/</g, "&lt;")}</div>`
                : ""
            }
            ${
              tags.length
                ? `<div class="popup-tags">${tags
                    .map((t) => `<span class="tag">${t}</span>`)
                    .join("")}</div>`
                : ""
            }
          </div>`;

        const marker = new maplibregl.Marker({ element: el })
          .setLngLat([s.lng, s.lat])
          .setPopup(new maplibregl.Popup({ offset: 18 }).setHTML(popupHtml))
          .addTo(map);
        markers.push(marker);
      }
    };

    if (map.isStyleLoaded()) addMarkers();
    else map.once("load", addMarkers);

    return () => {
      markers.forEach((m) => m.remove());
    };
  }, [sightings]);

  return <div ref={containerRef} className="map-wrap" />;
}
