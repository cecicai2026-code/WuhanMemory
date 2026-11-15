/**
 * 地点档案页面用到的小部件：纸上的一个条目、来源和核实日期那一行、图册、连不上后端时的提示。
 * 都是服务器组件，当前语言的 t（lib/i18n-server.ts 的 getT）由页面传进来。
 */
import type { ReactNode } from "react";
import type { FoodItem, PhotoSpot, PoiFact, PoiPhoto, Review } from "@wuhanmemory/shared";
import { Paper, PaperTitle, PencilNote, Soft } from "@/components/ui";
import { SOURCE_TYPE_TEXT, VERIFICATION_TEXT, both, formatDate } from "@/lib/format-poi";
import type { T } from "@/lib/i18n";
import { photoUrl } from "@/lib/places";
import s from "./places.module.css";

/** 一条信息下面的小字：怎么核实的、来源、核实日期、有效期。条目旁不盖章，章只盖在整张纸的右下角 */
export function FactMeta({ fact, t }: { fact: PoiFact<unknown>; t: T }) {
  if (fact.status === "missing") return null;
  const src = fact.source;
  return (
    <span className={s.meta}>
      <span>{both(VERIFICATION_TEXT[fact.verification], t)}</span>
      {src && (
        <span>
          {t(`来源（${SOURCE_TYPE_TEXT[src.type].zh}）：`, `Source (${SOURCE_TYPE_TEXT[src.type].en}): `)}
          {src.url ? (
            <a href={src.url} target="_blank" rel="noreferrer">
              {src.title}
            </a>
          ) : (
            src.title
          )}
        </span>
      )}
      {fact.extraSources.map((e) => (
        <span key={e.id}>
          {t(`另见（${SOURCE_TYPE_TEXT[e.type].zh}）：`, `See also (${SOURCE_TYPE_TEXT[e.type].en}): `)}
          {e.url ? (
            <a href={e.url} target="_blank" rel="noreferrer">
              {e.title}
            </a>
          ) : (
            e.title
          )}
        </span>
      ))}
      {fact.lastCheckedAt && <span>{t("核实于", "Checked")} {formatDate(fact.lastCheckedAt)}</span>}
      {fact.expiresAt && (
        <span className={fact.status === "expired" ? s.metaExpired : undefined}>
          {fact.status === "expired" ? t("已于", "Expired") : t("有效至", "Valid until")} {formatDate(fact.expiresAt)}
          {fact.status === "expired" ? t(" 过期", "") : ""}
        </span>
      )}
    </span>
  );
}

/** 纸上的一个条目。没有资料时写"待补充" */
export function Entry({ label, fact, t, children }: { label: string; fact: PoiFact<unknown>; t: T; children?: ReactNode }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {fact.status === "missing" || fact.value == null ? (
          <PencilNote>{t("待补充", "To fill in")}</PencilNote>
        ) : (
          <>
            <span className={s.value}>{children}</span>
            <FactMeta fact={fact} t={t} />
          </>
        )}
      </dd>
    </div>
  );
}

/** 一个条目下有好几项（拍照机位、周边美食），每项各有来源和日期 */
export function ListEntry<V>({
  label,
  facts,
  render,
  t
}: {
  label: string;
  facts: Array<PoiFact<V>>;
  render: (value: V) => ReactNode;
  t: T;
}) {
  const shown = facts.filter((f) => f.status !== "missing" && f.value != null);
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {shown.length === 0 ? (
          <PencilNote>{t("待补充", "To fill in")}</PencilNote>
        ) : (
          <ul className={s.items}>
            {shown.map((f, i) => (
              <li key={i}>
                <span className={s.value}>{render(f.value as V)}</span>
                <FactMeta fact={f} t={t} />
              </li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}

export function renderPhotoSpot(spot: PhotoSpot, t: T) {
  return (
    <>
      <strong>{spot.title}</strong>
      {t("：", ": ")}
      {spot.description}
    </>
  );
}

export function renderFood(item: FoodItem, t: T) {
  const walk = item.walkMinutes != null ? t(`，步行约 ${item.walkMinutes} 分钟`, `, about ${item.walkMinutes} min walk`) : "";
  return (
    <>
      <strong>{item.name}</strong>
      {walk}
      {item.note ? t(`。${item.note}`, `. ${item.note}`) : ""}
    </>
  );
}

/** 去过的人说：只用署名的真实评价 */
export function ReviewsEntry({ reviews, label, t }: { reviews: Review[]; label: string; t: T }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {reviews.length === 0 ? (
          <PencilNote>{t("待补充", "To fill in")}</PencilNote>
        ) : (
          <ul className={s.items}>
            {reviews.map((r, i) => (
              <li key={i}>
                <span className={s.value}>“{r.text}”</span>
                <span className={s.meta}>
                  <span>
                    {r.author}
                    {t(`（${r.relation === "self" ? "本人" : "朋友"}）`, ` (${r.relation === "self" ? "the author" : "a friend"})`)}
                  </span>
                  <span>{t(`${formatDate(r.visitedAt)} 去过`, `Visited ${formatDate(r.visitedAt)}`)}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </dd>
    </div>
  );
}

/** 景点图册。占位照片（官网的，或图库、媒体的）标"占位"并写明图片来源和授权情况 */
export function GalleryEntry({ photos, label, t }: { photos: PoiPhoto[]; label: string; t: T }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        {photos.length === 0 ? (
          <PencilNote>{t("待补充", "To fill in")}</PencilNote>
        ) : (
          <ul className={s.gallery}>
            {photos.map((p) => {
              // 纸上的照片不大，用 800 宽的缩略图（板块 1B）
              const src = photoUrl(p.url ? (p.thumbUrl ?? p.url) : null);
              return (
                <li key={p.file}>
                  <figure className={s.photo}>
                    {src ? (
                      // 照片来自后端的 /media/，尺寸不固定，用普通 img
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={src} alt={p.caption} loading="lazy" />
                    ) : (
                      <span className={s.photoMissing}>
                        <PencilNote>{t("占位照片不在本机", "Placeholder photo not on this machine")}</PencilNote>
                      </span>
                    )}
                    <figcaption>
                      {p.caption}
                      <span className={s.meta}>
                        {p.placeholder ? (
                          <>
                            <PencilNote>{t("占位", "Placeholder")}</PencilNote>
                            {p.sourceUrl && (
                              <span>
                                {t("图片来源：", "Image source: ")}
                                <a href={p.sourceUrl} target="_blank" rel="noreferrer">
                                  {p.license === "third-party-placeholder" ? (p.author ?? t("来源链接", "source link")) : t("官方页面", "official page")}
                                </a>
                              </span>
                            )}
                            {p.license === "third-party-placeholder" && p.licenseNote && <span>{p.licenseNote}</span>}
                            {p.retrievedAt && <span>{t("下载于", "Downloaded")} {formatDate(p.retrievedAt)}</span>}
                          </>
                        ) : (
                          <>
                            {p.author && <span>{t(`${p.author} 摄`, `Photo: ${p.author}`)}</span>}
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
export function ApiDown({ message, t }: { message: string; t: T }) {
  return (
    <Paper className={s.notice}>
      <PaperTitle level={3}>{t("景点资料暂时取不到", "Place data can't be fetched right now")}</PaperTitle>
      {process.env.NODE_ENV === "development" ? (
        <>
          <p>{t(`${message}。景点数据由后端提供，请先启动后端：`, `${message}. Place data comes from the backend; start it first:`)}</p>
          <pre className={s.command}>cd ~/WuhanMemory-project2 && corepack pnpm dev:api</pre>
          <Soft>{t("启动后刷新这一页。", "Then refresh this page.")}</Soft>
        </>
      ) : (
        <p>{t("网站的后台暂时连不上，请稍后刷新这一页。", "The site's backend can't be reached right now. Please refresh this page later.")}</p>
      )}
    </Paper>
  );
}
