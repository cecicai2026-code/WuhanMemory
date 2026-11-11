"use client";

import { Box, Layers3, Map, Navigation, TrainFront, WalletCards } from "lucide-react";
import type { ItineraryDay, ItineraryVersion, MapPoi, RouteSegment } from "@wuhanmemory/shared";

interface MockMapProps {
  itinerary: ItineraryVersion;
  day: ItineraryDay;
  mode: "2d" | "3d";
  selectedPoiId: string;
  onModeChange: (mode: "2d" | "3d") => void;
  onSelectPoi: (poiId: string) => void;
}

interface NormalizedPoint {
  x: number;
  y: number;
}

function normalize(point: { lng: number; lat: number }, pois: MapPoi[]): NormalizedPoint {
  const lngs = pois.map((poi) => poi.location.lng);
  const lats = pois.map((poi) => poi.location.lat);
  const minLng = Math.min(...lngs) - 0.01;
  const maxLng = Math.max(...lngs) + 0.01;
  const minLat = Math.min(...lats) - 0.01;
  const maxLat = Math.max(...lats) + 0.01;

  return {
    x: ((point.lng - minLng) / (maxLng - minLng)) * 100,
    y: (1 - (point.lat - minLat) / (maxLat - minLat)) * 100
  };
}

function modeLabel(mode: RouteSegment["mode"]) {
  const labels: Record<RouteSegment["mode"], string> = {
    walk: "步行",
    metro: "地铁",
    taxi: "打车",
    ferry: "轮渡",
    bike: "骑行"
  };
  return labels[mode];
}

export function MockMap({
  itinerary,
  day,
  mode,
  selectedPoiId,
  onModeChange,
  onSelectPoi
}: MockMapProps) {
  const dayPoiIds = new Set(day.stops.map((stop) => stop.poiId));
  const dayPois = itinerary.map.pois.filter((poi) => dayPoiIds.has(poi.id));
  const allPois = itinerary.map.pois;

  const routePath = day.routeSegments
    .flatMap((segment) => segment.polyline)
    .map((point) => normalize(point, allPois))
    .map((point) => `${point.x},${point.y}`)
    .join(" ");

  const totalMinutes = day.routeSegments.reduce(
    (sum, segment) => sum + segment.durationMinutes,
    0
  );
  const totalCost = day.routeSegments.reduce(
    (sum, segment) => sum + (segment.costEstimateCny ?? 0),
    0
  );

  return (
    <div className={`mock-map mode-${mode}`}>
      <div className="map-toolbar">
        <div className="segmented-control" aria-label="地图模式">
          <button
            type="button"
            className={mode === "2d" ? "active" : ""}
            onClick={() => onModeChange("2d")}
            aria-label="切换到 2D 地图"
          >
            <Map aria-hidden="true" size={18} />
            <span>2D</span>
          </button>
          <button
            type="button"
            className={mode === "3d" ? "active" : ""}
            onClick={() => onModeChange("3d")}
            aria-label="切换到 3D 地图"
          >
            <Box aria-hidden="true" size={18} />
            <span>3D</span>
          </button>
        </div>
        <div className="map-stat">
          <TrainFront aria-hidden="true" size={17} />
          <span>{totalMinutes} min</span>
        </div>
        <div className="map-stat">
          <WalletCards aria-hidden="true" size={17} />
          <span>约 {totalCost} 元</span>
        </div>
      </div>

      <div className="map-stage">
        <div className="river river-a" />
        <div className="river river-b" />
        <div className="park park-a" />
        <div className="park park-b" />
        <div className="district-label label-wuchang">武昌</div>
        <div className="district-label label-hankou">汉口</div>
        <div className="district-label label-eastlake">东湖</div>

        <svg className="route-layer" viewBox="0 0 100 100" preserveAspectRatio="none">
          <polyline points={routePath} />
        </svg>

        {dayPois.map((poi, index) => {
          const point = normalize(poi.location, allPois);
          return (
            <button
              type="button"
              key={poi.id}
              className={`map-marker ${selectedPoiId === poi.id ? "selected" : ""}`}
              style={{ left: `${point.x}%`, top: `${point.y}%` }}
              onClick={() => onSelectPoi(poi.id)}
              aria-label={`查看 ${poi.name}`}
            >
              <span>{index + 1}</span>
            </button>
          );
        })}
      </div>

      <div className="route-strip">
        <Layers3 aria-hidden="true" size={18} />
        <span>{day.theme}</span>
        <Navigation aria-hidden="true" size={17} />
        <span>{day.routeSegments.map((segment) => modeLabel(segment.mode)).join(" / ")}</span>
      </div>
    </div>
  );
}
