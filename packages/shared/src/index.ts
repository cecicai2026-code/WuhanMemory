export type TransportMode = "walk" | "metro" | "taxi" | "ferry" | "bike";
export type Pace = "relaxed" | "moderate" | "intensive";
export type BudgetLevel = "low" | "medium" | "high";

export interface GeoPoint {
  lng: number;
  lat: number;
}

export interface MapPoi {
  id: string;
  name: string;
  district: string;
  category: string;
  location: GeoPoint;
  tags: string[];
  recommendedDurationMinutes: number;
  intro: string;
  history: string;
  reviewSummary: string;
  photoTips: string[];
  reservationTips: string[];
  paymentTips: string[];
  source: {
    name: string;
    lastVerifiedAt: string;
  };
}

export interface RouteSegment {
  id: string;
  fromPoiId: string;
  toPoiId: string;
  mode: TransportMode;
  durationMinutes: number;
  distanceMeters: number;
  costEstimateCny: number | null;
  source: string;
  polyline: GeoPoint[];
}

export interface DayStop {
  poiId: string;
  startTime: string;
  endTime: string;
  reason: string;
}

export interface ItineraryDay {
  dayNumber: number;
  date: string;
  theme: string;
  summary: string;
  stops: DayStop[];
  routeSegments: RouteSegment[];
}

export interface TravelerProfile {
  pace: Pace;
  interests: string[];
  transportPreference: string;
  budgetLevel: BudgetLevel;
  partyType: string;
}

export interface ItineraryVersion {
  id: string;
  itineraryId: string;
  versionNumber: number;
  title: string;
  city: string;
  dateRange: {
    start: string;
    end: string;
  };
  travelerProfile: TravelerProfile;
  days: ItineraryDay[];
  map: {
    pois: MapPoi[];
  };
  validation: {
    status: "passed" | "warning" | "failed";
    warnings: string[];
  };
  plannerTrace: {
    provider: "mock" | "qwen" | "doubao";
    model: string;
    generatedAt: string;
  };
}

export interface ConversationResponse {
  conversationId: string;
  status: "active";
}

export interface PlanningJobResponse {
  messageId: string;
  planningJobId: string;
  itineraryVersionId: string;
  status: "queued" | "running" | "completed" | "failed";
}

export interface ShareResponse {
  shareId: string;
  slug: string;
  url: string;
}

// 景点接口（板块 2）
export * from "./poi";
export * from "./route";
