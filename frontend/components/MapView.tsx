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

function gridFeatures(centerLon: number, centerLat: number) {
  const features: object[] = [];
  for (let offset = -4; offset <= 4; offset += 1) {
    const lon = centerLon + offset * 2;
    const lat = centerLat + offset * 1.25;
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: [[lon, centerLat - 5], [lon, centerLat + 5]] },
      properties: {},
    });
    features.push({
      type: "Feature",
      geometry: { type: "LineString", coordinates: [[centerLon - 8, lat], [centerLon + 8, lat]] },
      properties: {},
    });
  }
  return features;
}

export default function MapView({ events, incidents, facilities, selectedEvent, selectedPlan }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("maplibre-gl").Map | null>(null);
  const loadedRef = useRef(false);
  const focusedEventRef = useRef<string | null>(null);
  const dataRef = useRef({ events, incidents, facilities, selectedEvent, selectedPlan });
  dataRef.current = { events, incidents, facilities, selectedEvent, selectedPlan };

  useEffect(() => {
    let disposed = false;

    async function initialize() {
      const maplibre = await import("maplibre-gl");
      if (disposed || !containerRef.current || mapRef.current) return;

      const map = new maplibre.Map({
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
      mapRef.current = map;

      map.on("load", () => {
        if (disposed) return;
        loadedRef.current = true;
        map.addSource("aegis-grid", { type: "geojson", data: featureCollection([]) as never });
        map.addSource("aegis-events", { type: "geojson", data: featureCollection([]) as never });
        map.addSource("aegis-facilities", { type: "geojson", data: featureCollection([]) as never });
        map.addSource("aegis-routes", { type: "geojson", data: featureCollection([]) as never });
        map.addLayer({ id: "aegis-grid-layer", type: "line", source: "aegis-grid", paint: { "line-color": "#6f9278", "line-width": 1, "line-opacity": 0.13 } });
        map.addLayer({ id: "aegis-routes-layer", type: "line", source: "aegis-routes", paint: { "line-color": "#8bbf8c", "line-width": 1.5, "line-dasharray": [2, 2], "line-opacity": 0.7 } });
        map.addLayer({ id: "aegis-facilities-layer", type: "circle", source: "aegis-facilities", paint: { "circle-color": "#8bbf8c", "circle-radius": 6, "circle-stroke-color": "#0b0e0d", "circle-stroke-width": 2 } });
        map.addLayer({ id: "aegis-events-layer", type: "circle", source: "aegis-events", paint: { "circle-color": ["case", ["==", ["get", "synthetic"], true], "#e7a64b", "#d16b5c"], "circle-radius": ["interpolate", ["linear"], ["get", "magnitude"], 0, 6, 8, 18], "circle-stroke-color": "#f0f2ed", "circle-stroke-width": 1.5 } });
        syncMap(map);
      });

      function syncMap(currentMap: import("maplibre-gl").Map) {
        if (!loadedRef.current) return;
        const { events: currentEvents, incidents: currentIncidents, facilities: currentFacilities, selectedEvent: currentSelectedEvent, selectedPlan: currentSelectedPlan } = dataRef.current;
        const incidentPriority = new Map(currentIncidents.map((incident) => [incident.id, incident.priority]));
        const eventFeatures = currentEvents.map((event) => {
          const incident = currentIncidents.find((item) => item.event_ids.includes(event.id));
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
        const facilityFeatures = currentFacilities.map((facility) => ({
          type: "Feature",
          geometry: { type: "Point", coordinates: [facility.lon, facility.lat] },
          properties: { name: facility.name, type: facility.type },
        }));
        const selectedTargets = new Set(currentSelectedPlan?.actions.filter((action) => action.type === "stage_resources").map((action) => action.target));
        const routeFeatures = currentSelectedEvent
          ? currentFacilities.filter((facility) => selectedTargets.size === 0 || selectedTargets.has(facility.id)).map((facility) => ({
              type: "Feature",
              geometry: { type: "LineString", coordinates: [[currentSelectedEvent.lon, currentSelectedEvent.lat], [facility.lon, facility.lat]] },
              properties: {},
            }))
          : [];
        const centerLon = currentSelectedEvent?.lon ?? 85.3;
        const centerLat = currentSelectedEvent?.lat ?? 27.7;
        (currentMap.getSource("aegis-grid") as import("maplibre-gl").GeoJSONSource).setData(featureCollection(gridFeatures(centerLon, centerLat)) as never);
        (currentMap.getSource("aegis-events") as import("maplibre-gl").GeoJSONSource).setData(featureCollection(eventFeatures) as never);
        (currentMap.getSource("aegis-facilities") as import("maplibre-gl").GeoJSONSource).setData(featureCollection(facilityFeatures) as never);
        (currentMap.getSource("aegis-routes") as import("maplibre-gl").GeoJSONSource).setData(featureCollection(routeFeatures) as never);
        currentMap.resize();
        const focusedEventId = currentSelectedEvent?.id ?? null;
        if (focusedEventId !== focusedEventRef.current) {
          focusedEventRef.current = focusedEventId;
          if (currentSelectedEvent) currentMap.flyTo({ center: [currentSelectedEvent.lon, currentSelectedEvent.lat], zoom: 7, duration: 500 });
        }
      }

      const interval = window.setInterval(() => syncMap(map), 250);
      map.once("remove", () => window.clearInterval(interval));
    }

    void initialize();
    return () => {
      disposed = true;
      loadedRef.current = false;
      focusedEventRef.current = null;
      mapRef.current?.remove();
      mapRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    map.resize();
  }, [events, incidents, facilities, selectedEvent, selectedPlan]);

  return <div className="map-root" ref={containerRef} aria-label="Offline event and facility map" />;
}
