import { mockWuhanItinerary } from "@wuhanmemory/shared/mock";
import type {
  ConversationResponse,
  ItineraryVersion,
  PlanningJobResponse,
  ShareResponse
} from "@wuhanmemory/shared";

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      ...(init?.headers ?? {})
    },
    cache: "no-store"
  });

  if (!response.ok) {
    throw new Error(`API request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export async function getMockItinerary(): Promise<ItineraryVersion> {
  try {
    return await requestJson<ItineraryVersion>("/api/itinerary-versions/mock-wuhan-3-days");
  } catch {
    return mockWuhanItinerary;
  }
}

export async function createConversation(): Promise<ConversationResponse> {
  return requestJson<ConversationResponse>("/api/conversations", {
    method: "POST",
    body: JSON.stringify({
      city: "武汉",
      locale: "zh-CN"
    })
  });
}

export async function sendMessage(
  conversationId: string,
  content: string
): Promise<PlanningJobResponse> {
  return requestJson<PlanningJobResponse>(`/api/conversations/${conversationId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content })
  });
}

export async function getItineraryVersion(versionId: string): Promise<ItineraryVersion> {
  try {
    return await requestJson<ItineraryVersion>(`/api/itinerary-versions/${versionId}`);
  } catch {
    return mockWuhanItinerary;
  }
}

export async function publishSharePage(versionId: string): Promise<ShareResponse> {
  return requestJson<ShareResponse>(`/api/itinerary-versions/${versionId}/share`, {
    method: "POST",
    body: JSON.stringify({
      visibility: "public",
      expiresAt: null
    })
  });
}
