"use client";

import type { EventRecord, Facility, Incident, Plan } from "@/lib/types";

type MapViewProps = {
  events: EventRecord[];
  incidents: Incident[];
  facilities: Facility[];
  selectedEvent?: EventRecord;
  selectedPlan?: Plan;
};

type Point = { lon: number; lat: number };

function range(count: number) {
  return Array.from({ length: count }, (_, index) => index);
}

function getBounds(events: EventRecord[], facilities: Facility[], selectedEvent?: EventRecord) {
  const points: Point[] = [
    ...events.map((event) => ({ lon: event.lon, lat: event.lat })),
    ...facilities.map((facility) => ({ lon: facility.lon, lat: facility.lat })),
    ...(selectedEvent ? [{ lon: selectedEvent.lon, lat: selectedEvent.lat }] : []),
  ];
  if (points.length === 0) return { centerLon: 85.3, centerLat: 27.7, spanLon: 8, spanLat: 4.5 };

  const minLon = Math.min(...points.map((point) => point.lon));
  const maxLon = Math.max(...points.map((point) => point.lon));
  const minLat = Math.min(...points.map((point) => point.lat));
  const maxLat = Math.max(...points.map((point) => point.lat));
  const spanLat = Math.max(maxLat - minLat + 1.5, 4.5);
  const spanLon = Math.max(maxLon - minLon + 2, spanLat * 2.05, 8);

  return {
    centerLon: (minLon + maxLon) / 2,
    centerLat: (minLat + maxLat) / 2,
    spanLon,
    spanLat,
  };
}

function markerLabel(name: string) {
  return name.length > 22 ? `${name.slice(0, 21)}…` : name;
}

export default function MapView({ events, incidents, facilities, selectedEvent, selectedPlan }: MapViewProps) {
  const width = 1000;
  const height = 455;
  const bounds = getBounds(events, facilities, selectedEvent);
  const incidentPriority = new Map(incidents.map((incident) => [incident.id, incident.priority]));
  const selectedTargets = new Set(
    selectedPlan?.actions.filter((action) => action.type === "stage_resources").map((action) => action.target),
  );
  const projected = (point: Point) => ({
    x: ((point.lon - (bounds.centerLon - bounds.spanLon / 2)) / bounds.spanLon) * width,
    y: height - ((point.lat - (bounds.centerLat - bounds.spanLat / 2)) / bounds.spanLat) * height,
  });
  const routeFacilities = selectedEvent
    ? facilities.filter((facility) => selectedTargets.size === 0 || selectedTargets.has(facility.id))
    : [];

  return (
    <div className="map-root" aria-label="Offline event and facility map">
      <svg className="offline-map-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Offline operational vector map">
        <defs>
          <pattern id="map-hatch" width="18" height="18" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="18" stroke="#8bbf8c" strokeOpacity="0.05" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width={width} height={height} fill="#0d1210" />
        <rect width={width} height={height} fill="url(#map-hatch)" />
        {range(9).map((index) => {
          const x = (index / 8) * width;
          return <line className="map-grid-line" key={`v-${index}`} x1={x} y1="0" x2={x} y2={height} />;
        })}
        {range(6).map((index) => {
          const y = (index / 5) * height;
          return <line className="map-grid-line" key={`h-${index}`} x1="0" y1={y} x2={width} y2={y} />;
        })}
        <rect className="map-boundary" x="18" y="18" width={width - 36} height={height - 36} />
        <text className="map-north" x="width - 42" y="36" textAnchor="middle">N</text>
        <path className="map-north-arrow" d="M958 48 L958 74 M958 48 L952 58 M958 48 L964 58" />

        {routeFacilities.map((facility) => {
          const start = projected(selectedEvent as EventRecord);
          const end = projected(facility);
          return <line className="map-route" key={`route-${facility.id}`} x1={start.x} y1={start.y} x2={end.x} y2={end.y} />;
        })}

        {facilities.map((facility) => {
          const point = projected(facility);
          return (
            <g key={facility.id} className="map-facility-group">
              <circle className="map-facility" cx={point.x} cy={point.y} r="7" />
              <text className="map-label map-facility-label" x={point.x + 11} y={point.y + 3}>{markerLabel(facility.name)}</text>
            </g>
          );
        })}

        {events.map((event) => {
          const point = projected(event);
          const incident = incidents.find((item) => item.event_ids.includes(event.id));
          const priority = incident ? incidentPriority.get(incident.id) ?? 1 : 1;
          const selected = selectedEvent?.id === event.id;
          const radius = Math.max(7, Math.min(19, 6 + (event.magnitude ?? 0) * 1.5));
          return (
            <g key={event.id} className="map-event-group">
              {selected && <circle className="map-event-ring" cx={point.x} cy={point.y} r={radius + 10} />}
              <circle className={`map-event ${event.synthetic ? "map-event-synthetic" : ""}`} cx={point.x} cy={point.y} r={radius} />
              <text className="map-label map-event-label" x={point.x + radius + 8} y={point.y + 4}>
                {event.synthetic ? "SYNTHETIC" : `P${priority} / M${event.magnitude?.toFixed(1) ?? "—"}`}
              </text>
            </g>
          );
        })}

        {events.length === 0 && facilities.length === 0 && (
          <text className="map-empty-label" x={width / 2} y={height / 2} textAnchor="middle">OFFLINE VECTOR MAP READY</text>
        )}
        <text className="map-coordinate map-coordinate-left" x="28" y={height - 22}>{bounds.centerLat.toFixed(2)}° N</text>
        <text className="map-coordinate map-coordinate-right" x={width - 28} y={height - 22} textAnchor="end">{bounds.centerLon.toFixed(2)}° E</text>
      </svg>
    </div>
  );
}
