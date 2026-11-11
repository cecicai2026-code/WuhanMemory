"use client";

import { useEffect, useMemo, useState } from "react";
import type { ItineraryVersion, MapPoi } from "@wuhanmemory/shared";
import { mockWuhanItinerary } from "@wuhanmemory/shared/mock";
import { ChatPanel } from "@/features/chat/ChatPanel";
import { ItineraryTimeline } from "@/features/itinerary/ItineraryTimeline";
import { MockMap } from "@/features/map/MockMap";
import { SpotDetail } from "@/features/itinerary/SpotDetail";
import { getItineraryVersion, getMockItinerary } from "@/lib/api";

export function TravelWorkspace() {
  const [itinerary, setItinerary] = useState<ItineraryVersion>(mockWuhanItinerary);
  const [selectedDay, setSelectedDay] = useState(1);
  const [selectedPoiId, setSelectedPoiId] = useState(itinerary.days[0].stops[0].poiId);
  const [mapMode, setMapMode] = useState<"2d" | "3d">("2d");
  const [status, setStatus] = useState("mock itinerary ready");

  useEffect(() => {
    getMockItinerary()
      .then((data) => {
        setItinerary(data);
        setSelectedDay(data.days[0]?.dayNumber ?? 1);
        setSelectedPoiId(data.days[0]?.stops[0]?.poiId ?? data.map.pois[0]?.id);
      })
      .catch(() => setStatus("using local mock data"));
  }, []);

  const currentDay = useMemo(
    () => itinerary.days.find((day) => day.dayNumber === selectedDay) ?? itinerary.days[0],
    [itinerary, selectedDay]
  );

  const selectedPoi = useMemo<MapPoi | undefined>(
    () => itinerary.map.pois.find((poi) => poi.id === selectedPoiId),
    [itinerary.map.pois, selectedPoiId]
  );

  async function handlePlanningComplete(versionId: string) {
    setStatus("refreshing itinerary");
    const nextItinerary = await getItineraryVersion(versionId);
    setItinerary(nextItinerary);
    setSelectedDay(nextItinerary.days[0]?.dayNumber ?? 1);
    setSelectedPoiId(nextItinerary.days[0]?.stops[0]?.poiId ?? nextItinerary.map.pois[0]?.id);
    setStatus("mock provider completed");
  }

  return (
    <main className="workspace-shell">
      <section className="chat-column" aria-label="AI travel planning">
        <ChatPanel itinerary={itinerary} onPlanningComplete={handlePlanningComplete} />
      </section>

      <section className="map-column" aria-label="Map itinerary">
        <MockMap
          itinerary={itinerary}
          day={currentDay}
          mode={mapMode}
          selectedPoiId={selectedPoiId}
          onModeChange={setMapMode}
          onSelectPoi={setSelectedPoiId}
        />
      </section>

      <aside className="detail-column" aria-label="Itinerary details">
        <div className="status-row">
          <span>{itinerary.city}</span>
          <span>{status}</span>
        </div>
        <ItineraryTimeline
          itinerary={itinerary}
          selectedDay={selectedDay}
          selectedPoiId={selectedPoiId}
          onSelectDay={setSelectedDay}
          onSelectPoi={setSelectedPoiId}
        />
        {selectedPoi ? <SpotDetail poi={selectedPoi} /> : null}
      </aside>
    </main>
  );
}
