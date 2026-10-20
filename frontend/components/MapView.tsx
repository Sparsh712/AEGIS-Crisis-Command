"use client";

import { useEffect, useRef } from "react";
import type { EventRecord, Facility, Incident, Plan } from "@/lib/types";
import "maplibre-gl/dist/maplibre-gl.css";

type MapViewProps = {
  events: EventRecord[];
  incidents: Incident[];
  facilities: Facility[];
  selectedEvent?: EventRecord;
  selectedPlan?: Plan;
};

function featureCollection(features: object[]) {
  return { type: "FeatureCollection", features };
}

export default function MapView({ events, incidents, facilities, selectedEvent, selectedPlan }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let map: import("maplibre-gl").Map | undefined;
    let disposed = false;

    async function initialize() {
      const maplibre = await import("maplibre-gl");
      if (disposed || !containerRef.current) return;

      const incidentPriority = new Map(incidents.map((incident) => [incident.id, incident.priority]));
      const eventFeatures = events.map((event) => {
        const incident = incidents.find((item) => item.event_ids.includes(event.id));
        return {
          type: "Feature",
          geometry: { type: "Point", coordinates: [event.lon, event.lat] },
          properties: {
            magnitude: event.magnitude ?? 0,
            priority: incident ? incidentPriority.get(incident.id) ?? 1 : 1,
            synthetic: event.synthetic,
          },
        };
      });
      const facilityFeatures = facilities.map((facility) => ({
        type: "Feature",
        geometry: { type: "Point", coordinates: [facility.lon, facility.lat] },
        properties: { name: facility.name, type: facility.type },
      }));
      const selectedTargets = new Set(selectedPlan?.actions.filter((action) => action.type === "stage_resources").map((action) => action.target));
      const routeFeatures = selectedEvent
        ? facilities.filter((facility) => selectedTargets.size === 0 || selectedTargets.has(facility.id)).map((facility) => ({
            type: "Feature",
            geometry: { type: "LineString", coordinates: [[selectedEvent.lon, selectedEvent.lat], [facility.lon, facility.lat]] },
            properties: {},
          }))
        : [];

      map = new maplibre.Map({
        container: containerRef.current,
        attributionControl: false,
        center: selectedEvent ? [selectedEvent.lon, selectedEvent.lat] : [85.3, 27.7],
        zoom: selectedEvent ? 7 : 5,
        style: {
          version: 8,
          sources: {},
          layers: [{ id: "background", type: "background", paint: { "background-color": "#0d1210" } }],
        },
      });

      map.on("load", () => {
        if (!map) return;
        map.addSource("aegis-events", { type: "geojson", data: featureCollection(eventFeatures) as never });
        map.addSource("aegis-facilities", { type: "geojson", data: featureCollection(facilityFeatures) as never });
        map.addSource("aegis-routes", { type: "geojson", data: featureCollection(routeFeatures) as never });
        map.addLayer({ id: "aegis-routes-layer", type: "line", source: "aegis-routes", paint: { "line-color": "#8bbf8c", "line-width": 1.5, "line-dasharray": [2, 2], "line-opacity": 0.7 } });
        map.addLayer({ id: "aegis-facilities-layer", type: "circle", source: "aegis-facilities", paint: { "circle-color": "#8bbf8c", "circle-radius": 6, "circle-stroke-color": "#0b0e0d", "circle-stroke-width": 2 } });
        map.addLayer({ id: "aegis-events-layer", type: "circle", source: "aegis-events", paint: { "circle-color": ["case", ["==", ["get", "synthetic"], true], "#e7a64b", "#d16b5c"], "circle-radius": ["interpolate", ["linear"], ["get", "magnitude"], 0, 6, 8, 18], "circle-stroke-color": "#f0f2ed", "circle-stroke-width": 1.5 } });
        if (selectedEvent) {
          map.flyTo({ center: [selectedEvent.lon, selectedEvent.lat], zoom: 7, duration: 500 });
        }
      });
    }

    void initialize();
    return () => {
      disposed = true;
      map?.remove();
    };
  }, [events, incidents, facilities, selectedEvent, selectedPlan]);

  return <div className="map-root" ref={containerRef} aria-label="Offline event and facility map" />;
}
