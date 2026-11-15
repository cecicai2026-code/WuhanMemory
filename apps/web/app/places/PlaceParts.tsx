/**
 * 地点档案页面用到的小部件：纸上的一个条目、来源和核实日期那一行、图册、连不上后端时的提示。
 */
import type { ReactNode } from "react";
import type { FoodItem, PhotoSpot, PoiFact, PoiPhoto, Review } from "@wuhanmemory/shared";
import { Paper, PaperTitle, PencilNote, Soft } from "@/components/ui";
import { SOURCE_TYPE_TEXT, VERIFICATION_TEXT, formatDate } from "@/lib/format-poi";
import { photoUrl } from "@/lib/places";
import s from "./places.module.css";

/** 一条信息下面的小字：怎么核实的、来源、核实日期、有效期。条目旁不盖章，章只盖在整张纸的右下角 */
export function FactMeta({ fact }: { fact: PoiFact<unknown> }) {
  if (fact.status === "missing") return null;
  const src = fact.source;
  return (
    <span className={s.meta}>
      <span>{VERIFICATION_TEXT[fact.verification]}</span>
      {src && (
        <span>
          来源（{SOURCE_TYPE_TEXT[src.type]}）：
          {src.url ? (
            <a href={src.url} target="_blank" rel="noreferrer">
              {src.title}
            </a>
          ) : (
            src.title
          )}
        </span>
      )}
      {fact.lastCheckedAt && <span>核实于 {formatDate(fact.lastCheckedAt)}</span>}
      {fact.expiresAt && (
        <span className={fact.status === "expired" ? s.metaExpired : undefined}>
          {fact.status === "expired" ? "已于" : "有效至"} {formatDate(fact.expiresAt)}
          {fact.status === "expired" ? " 过期" : ""}
        </span>
      )}
    </span>
  );
}

/** 纸上的一个条目。没有资料时写"待补充" */
export function Entry({ label, fact, children }: { label: string; fact: PoiFact<unknown>; children?: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {fact.status === "missing" || fact.value == null ? (
          <PencilNote>待补充</PencilNote>
        ) : (
          <>
            <span className={s.value}>{children}</span>
            <FactMeta fact={fact} />
          </>
        )}
      </dd>
    </div>
  );
}

/** 一个条目下有好几项（拍照机位、周边美食），每项各有来源和日期 */
export function ListEntry<T>({
  label,
  facts,
  render
}: {
  label: string;
  facts: Array<PoiFact<T>>;
  render: (value: T) => ReactNode;
}) {
  const shown = facts.filter((f) => f.status !== "missing" && f.value != null);
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {shown.length === 0 ? (
          <PencilNote>待补充</PencilNote>
        ) : (
          <ul className={s.items}>
            {shown.map((f, i) => (
              <li key={i}>
                <span className={s.value}>{render(f.value as T)}</span>
                <FactMeta fact={f} />
              </li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}

export function renderPhotoSpot(spot: PhotoSpot) {
  return (
    <>
      <strong>{spot.title}</strong>：{spot.description}
    </>
  );
}

export function renderFood(item: FoodItem) {
  const walk = item.walkMinutes != null ? `，步行约 ${item.walkMinutes} 分钟` : "";
  return (
    <>
      <strong>{item.name}</strong>
      {walk}
      {item.note ? `。${item.note}` : ""}
    </>
  );
}

/** 去过的人说：只用署名的真实评价 */
export function ReviewsEntry({ reviews }: { reviews: Review[] }) {
  return (
    <div>
      <dt>去过的人说</dt>
      <dd>
        {reviews.length === 0 ? (
          <PencilNote>待补充</PencilNote>
        ) : (
          <ul className={s.items}>
            {reviews.map((r, i) => (
              <li key={i}>
                <span className={s.value}>“{r.text}”</span>
                <span className={s.meta}>
                  <span>
                    {r.author}（{r.relation === "self" ? "本人" : "朋友"}）
                  </span>
                  <span>{formatDate(r.visitedAt)} 去过</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}

/** 景点图册。官网占位照片标"占位"并写明图片来源 */
export function GalleryEntry({ photos }: { photos: PoiPhoto[] }) {
  return (
    <div>
      <dt>照片</dt>
      <dd>
        {photos.length === 0 ? (
          <PencilNote>待补充</PencilNote>
        ) : (
          <ul className={s.gallery}>
            {photos.map((p) => {
              const src = photoUrl(p.url);
              return (
                <li key={p.file}>
                  <figure className={s.photo}>
                    {src ? (
                      // 照片来自后端的 /media/，尺寸不固定，用普通 img
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={src} alt={p.caption} loading="lazy" />
                    ) : (
                      <span className={s.photoMissing}>
                        <PencilNote>占位照片不在本机</PencilNote>
                      </span>
                    )}
                    <figcaption>
                      {p.caption}
                      <span className={s.meta}>
                        {p.placeholder ? (
                          <>
                            <PencilNote>占位</PencilNote>
                            {p.sourceUrl && (
                              <span>
                                图片来源：
                                <a href={p.sourceUrl} target="_blank" rel="noreferrer">
                                  官方页面
                                </a>
                              </span>
                            )}
                            {p.retrievedAt && <span>下载于 {formatDate(p.retrievedAt)}</span>}
                          </>
                        ) : (
                          <>
                            {p.author && <span>{p.author} 摄</span>}
                            {p.takenAt && <span>{formatDate(p.takenAt)}</span>}
                            {p.licenseNote && <span>{p.licenseNote}</span>}
                          </>
                        )}
                      </span>
                    </figcaption>
                  </figure>
                </li>
              );
            })}
          </ul>
        )}
      </dd>
    </div>
  );
}

/** 连不上后端时显示，告诉人怎么启动 */
export function ApiDown({ message }: { message: string }) {
  return (
    <Paper className={s.notice}>
      <PaperTitle level={3}>景点资料暂时取不到</PaperTitle>
      <p>{message}。景点数据由后端提供，请先启动后端：</p>
      <pre className={s.command}>cd ~/WuhanMemory-project2 && corepack pnpm dev:api</pre>
      <Soft>启动后刷新这一页。</Soft>
    </Paper>
  );
}
