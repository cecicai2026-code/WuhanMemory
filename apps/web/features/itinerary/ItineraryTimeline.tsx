"use client";

import { Camera, Clock, Route } from "lucide-react";
import type { ItineraryVersion } from "@wuhanmemory/shared";

interface ItineraryTimelineProps {
  itinerary: ItineraryVersion;
  selectedDay: number;
  selectedPoiId: string;
  onSelectDay: (dayNumber: number) => void;
  onSelectPoi: (poiId: string) => void;
}

export function ItineraryTimeline({
  itinerary,
  selectedDay,
  selectedPoiId,
  onSelectDay,
  onSelectPoi
}: ItineraryTimelineProps) {
  const day = itinerary.days.find((item) => item.dayNumber === selectedDay) ?? itinerary.days[0];

  return (
    <section className="timeline-panel">
      <div className="day-tabs" aria-label="行程天数">
        {itinerary.days.map((item) => (
          <button
            type="button"
            key={item.dayNumber}
            className={item.dayNumber === selectedDay ? "active" : ""}
            onClick={() => onSelectDay(item.dayNumber)}
          >
            D{item.dayNumber}
          </button>
        ))}
      </div>

      <div className="day-heading">
        <p>{day.date}</p>
        <h2>{day.theme}</h2>
        <span>{day.summary}</span>
      </div>

      <div className="stop-list">
        {day.stops.map((stop) => {
          const poi = itinerary.map.pois.find((item) => item.id === stop.poiId);
          if (!poi) {
            return null;
          }

          return (
            <button
              type="button"
              className={`stop-row ${selectedPoiId === poi.id ? "active" : ""}`}
              key={stop.poiId}
              onClick={() => onSelectPoi(poi.id)}
            >
              <span className="stop-time">
                <Clock aria-hidden="true" size={15} />
                {stop.startTime}
              </span>
              <span className="stop-main">
                <strong>{poi.name}</strong>
                <span>{stop.reason}</span>
              </span>
              <Camera aria-hidden="true" size={16} />
            </button>
          );
        })}
      </div>

      <div className="segment-list">
        {day.routeSegments.map((segment) => (
          <div className="segment-row" key={segment.id}>
            <Route aria-hidden="true" size={15} />
            <span>{segment.durationMinutes} min</span>
            <span>{Math.round(segment.distanceMeters / 100) / 10} km</span>
            <span>{segment.costEstimateCny === 0 ? "免费" : `约 ${segment.costEstimateCny} 元`}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
