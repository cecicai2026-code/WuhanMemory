import { ExternalLink, MapPinned } from "lucide-react";
import { mockWuhanItinerary } from "@wuhanmemory/shared/mock";

interface ShareViewProps {
  slug: string;
}

export function ShareView({ slug }: ShareViewProps) {
  const itinerary = mockWuhanItinerary;

  return (
    <main className="share-shell">
      <section className="share-header">
        <div>
          <p className="eyebrow">share · {slug}</p>
          <h1>{itinerary.title}</h1>
          <span>
            {itinerary.dateRange.start} - {itinerary.dateRange.end}
          </span>
        </div>
        <a href="/" aria-label="打开规划工作台">
          <ExternalLink aria-hidden="true" size={18} />
          <span>工作台</span>
        </a>
      </section>

      <section className="share-map">
        <MapPinned aria-hidden="true" size={28} />
        <span>{itinerary.city}</span>
      </section>

      <section className="share-days">
        {itinerary.days.map((day) => (
          <article className="share-day" key={day.dayNumber}>
            <p>D{day.dayNumber}</p>
            <h2>{day.theme}</h2>
            <span>{day.summary}</span>
            <ol>
              {day.stops.map((stop) => {
                const poi = itinerary.map.pois.find((item) => item.id === stop.poiId);
                return (
                  <li key={stop.poiId}>
                    <strong>{stop.startTime}</strong>
                    <span>{poi?.name}</span>
                  </li>
                );
              })}
            </ol>
          </article>
        ))}
      </section>
    </main>
  );
}
