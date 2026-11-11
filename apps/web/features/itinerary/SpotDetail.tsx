import { Camera, CircleDollarSign, Info, Landmark, Ticket } from "lucide-react";
import type { MapPoi } from "@wuhanmemory/shared";

interface SpotDetailProps {
  poi: MapPoi;
}

export function SpotDetail({ poi }: SpotDetailProps) {
  return (
    <section className="spot-panel">
      <div className="spot-heading">
        <p>{poi.district}</p>
        <h2>{poi.name}</h2>
        <span>{poi.category}</span>
      </div>

      <div className="tag-row">
        {poi.tags.map((tag) => (
          <span key={tag}>{tag}</span>
        ))}
      </div>

      <DetailBlock icon={<Info size={17} aria-hidden="true" />} title="简介" body={poi.intro} />
      <DetailBlock icon={<Landmark size={17} aria-hidden="true" />} title="历史文化" body={poi.history} />
      <DetailBlock
        icon={<Camera size={17} aria-hidden="true" />}
        title="拍照机位"
        body={poi.photoTips.join("；")}
      />
      <DetailBlock
        icon={<Ticket size={17} aria-hidden="true" />}
        title="预约提示"
        body={poi.reservationTips.length > 0 ? poi.reservationTips.join("；") : "暂无强预约提示"}
      />
      <DetailBlock
        icon={<CircleDollarSign size={17} aria-hidden="true" />}
        title="支付方式"
        body={poi.paymentTips.join("；")}
      />

      <p className="source-line">
        {poi.source.name} · {poi.source.lastVerifiedAt}
      </p>
    </section>
  );
}

function DetailBlock({
  icon,
  title,
  body
}: {
  icon: React.ReactNode;
  title: string;
  body: string;
}) {
  return (
    <div className="detail-block">
      <div>
        {icon}
        <strong>{title}</strong>
      </div>
      <p>{body}</p>
    </div>
  );
}
