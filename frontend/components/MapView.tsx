import { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { Event } from "../lib/api";

const getEventIcon = (color: string) => {
  return L.divIcon({
    html: `<span style="background-color: ${color}; width: 20px; height: 20px; display: block; border-radius: 50%; border: 3px solid #ffffff; box-shadow: 0 0 10px rgba(0,0,0,0.8);"></span>`,
    className: "custom-div-icon",
    iconSize: [20, 20],
    iconAnchor: [10, 10]
  });
};

const getBarricadeIcon = () => {
  return L.divIcon({
    html: `<div style="background-color: #a855f7; width: 18px; height: 18px; transform: rotate(45deg); display: block; border: 3px solid #ffffff; box-shadow: 0 0 8px rgba(0,0,0,0.8);"></div>`,
    className: "custom-barricade-icon",
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  });
};

const getSignalIcon = () => {
  return L.divIcon({
    html: `<div style="background-color: #06b6d4; width: 18px; height: 18px; border-radius: 4px; display: block; border: 3px solid #ffffff; box-shadow: 0 0 8px rgba(0,0,0,0.8);"></div>`,
    className: "custom-signal-icon",
    iconSize: [18, 18],
    iconAnchor: [9, 9]
  });
};

function ChangeView({ center }: { center: [number, number] }) {
  const map = useMap();
  useEffect(() => {
    if (center) {
      map.setView(center, 12);
    }
  }, [center, map]);
  return null;
}

interface MapViewProps {
  events: Event[];
  selectedEventId: string | null;
  onEventSelect: (eventId: string) => void;
  barricades?: { lat: number; lng: number; junction_name: string }[];
  diversions?: { route_polyline?: [number, number][]; polyline?: [number, number][]; description?: string }[];
  signals?: { lat: number; lng: number; signal_id: string; recommended_action: string }[];
}

export default function MapView({
  events,
  selectedEventId,
  onEventSelect,
  barricades = [],
  diversions = [],
  signals = []
}: MapViewProps) {
  const defaultCenter: [number, number] = [12.9716, 77.5946];
  const selectedEvent = events.find(e => e.event_id === selectedEventId);
  const center: [number, number] = selectedEvent
    ? [selectedEvent.latitude, selectedEvent.longitude]
    : defaultCenter;

  const getMarkerColor = (event: Event) => {
    if (event.event_type === "planned") {
      return "#3b82f6"; // distinct neutral blue for planned
    }
    const val = event.disruption_class || event.priority || "";
    switch (val) {
      case "Critical": return "#ef4444";
      case "High": return "#f97316";
      case "Medium": return "#f59e0b";
      case "Low": return "#22c55e";
      default: return "#22c55e";
    }
  };

  return (
    <div className="w-full h-full relative">
      <MapContainer
        center={defaultCenter}
        zoom={11}
        className="w-full h-full dark-tiles"
      >
        <ChangeView center={center} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {events.map((event) => {
          const color = getMarkerColor(event);
          return (
            <Marker
              key={event.event_id}
              position={[event.latitude, event.longitude]}
              icon={getEventIcon(color)}
              eventHandlers={{
                click: () => onEventSelect(event.event_id),
              }}
            >
              <Popup>
                <div className="text-slate-900 font-sans p-1">
                  <h3 className="font-bold text-sm mb-1">{event.corridor || "Bengaluru Corridor"}</h3>
                  <p className="text-xs text-slate-700 capitalize mb-1">
                    <strong>Type:</strong> {event.event_type} | <strong>Cause:</strong> {event.event_cause.replace('_', ' ')}
                  </p>
                  <p className="text-xs text-slate-700">
                    {event.description || "Traffic disruption event."}
                  </p>
                </div>
              </Popup>
            </Marker>
          );
        })}

        {barricades?.map((b, idx) => (
          <Marker
            key={`barricade-${idx}`}
            position={[b.lat, b.lng]}
            icon={getBarricadeIcon()}
          >
            <Popup>
              <div className="text-slate-900 font-sans p-1 text-xs">
                <span className="font-bold text-purple-700">Recommended Barricade</span>
                <div>{b.junction_name}</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {signals?.map((s, idx) => (
          <Marker
            key={`signal-${idx}`}
            position={[s.lat, s.lng]}
            icon={getSignalIcon()}
          >
            <Popup>
              <div className="text-slate-900 font-sans p-1 text-xs">
                <span className="font-bold text-cyan-700">Manual Signal Override</span>
                <div>Signal ID: {s.signal_id}</div>
                <div>Action: {s.recommended_action}</div>
              </div>
            </Popup>
          </Marker>
        ))}

        {diversions?.map((d, idx) => {
          // 1. Safely grab the data, falling back to 'polyline' if it's an older record
          const positions = d.route_polyline || (d as any).polyline;

          // Component Defensiveness: Validate that polyline is a valid array of coordinate pairs
          const polyline = (d as any).route_polyline || (d as any).polyline;
          if (!Array.isArray(polyline) || polyline.some(coord => !Array.isArray(coord) || coord.length < 2)) {
            console.warn("Invalid polyline format ignored:", polyline);
            return null;
          }
          return (
            <Polyline
              key={`diversion-${idx}`}
              positions={polyline}
              color="#a855f7"
              weight={6}
              opacity={0.9}
            />
          );
        })}
      </MapContainer>
    </div>
  );
}
