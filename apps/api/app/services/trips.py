"""我的行程（板块 7）：把 /map 上生成的行程按对话分组，带每个版本的分享链接。

只读数据库，不调用模型和高德。
"""

from __future__ import annotations

from app.repositories.conversation_repository import ConversationRepository
from app.repositories.itinerary_repository import ItineraryRepository
from app.repositories.share_link_repository import ShareLinkRepository
from app.schemas.itinerary import ItineraryVersion
from app.schemas.share import ShareLinkOut
from app.schemas.trips import TripConversation, TripItinerary, TripVersionSummary
from app.services.planning.emphasis import EMPHASES

_EMPHASIS_ORDER = {eid: i for i, eid in enumerate(EMPHASES)}


def _summary(v: ItineraryVersion) -> TripVersionSummary:
    return TripVersionSummary(
        id=v.id,
        versionNumber=v.versionNumber,
        createdAt=v.createdAt,
        title=v.title,
        providerLabel=v.planner.providerLabel,
        model=v.planner.model,
        validationStatus=v.validation.status,
        errorCount=len(v.validation.errors),
        warningCount=len(v.validation.warnings),
        days=v.frame.days,
        startDate=v.frame.startDate,
        poiNames=[s.name for d in v.days for s in d.stops],
    )


class TripLister:
    def __init__(self, itineraries: ItineraryRepository, conversations: ConversationRepository, links: ShareLinkRepository):
        self.itineraries = itineraries
        self.conversations = conversations
        self.links = links

    def list(self) -> list[TripConversation]:
        by_conv: dict[str, list[tuple[str, list[ItineraryVersion]]]] = {}
        for ref in self.itineraries.list_conversation_itineraries():
            versions = self.itineraries.list_versions(ref.id)
            if versions and ref.conversationId:
                by_conv.setdefault(ref.conversationId, []).append((ref.id, versions))

        all_ids = [v.id for items in by_conv.values() for _, vs in items for v in vs]
        active = self.links.active_by_version(all_ids)

        out: list[TripConversation] = []
        for conv_id, items in by_conv.items():
            itineraries: list[TripItinerary] = []
            for itin_id, versions in items:
                emphasis = versions[-1].emphasis
                summaries = []
                for v in reversed(versions):
                    s = _summary(v)
                    link = active.get(v.id)
                    s.share = ShareLinkOut.of(link) if link else None
                    summaries.append(s)
                itineraries.append(
                    TripItinerary(
                        itineraryId=itin_id,
                        emphasis=emphasis,
                        emphasisLabel=EMPHASES[emphasis].label if emphasis in EMPHASES else None,
                        versions=summaries,
                    )
                )
            itineraries.sort(key=lambda i: _EMPHASIS_ORDER.get(i.emphasis or "", len(_EMPHASIS_ORDER)))
            first_user = next((m.content for m in self.conversations.messages(conv_id) if m.role == "user"), None)
            updated = max(v.createdAt for i in itineraries for v in i.versions)
            out.append(TripConversation(conversationId=conv_id, updatedAt=updated, request=first_user, itineraries=itineraries))
        out.sort(key=lambda t: t.updatedAt, reverse=True)
        return out
