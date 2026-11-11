from typing import Literal

from pydantic import BaseModel, Field


TransportMode = Literal["walk", "metro", "taxi", "ferry", "bike"]


class GeoPoint(BaseModel):
    lng: float
    lat: float


class SourceInfo(BaseModel):
    name: str
    lastVerifiedAt: str


class MapPoi(BaseModel):
    id: str
    name: str
    district: str
    category: str
    location: GeoPoint
    tags: list[str]
    recommendedDurationMinutes: int
    intro: str
    history: str
    reviewSummary: str
    photoTips: list[str]
    reservationTips: list[str]
    paymentTips: list[str]
    source: SourceInfo


class RouteSegment(BaseModel):
    id: str
    fromPoiId: str
    toPoiId: str
    mode: TransportMode
    durationMinutes: int
    distanceMeters: int
    costEstimateCny: float | None
    source: str
    polyline: list[GeoPoint]


class DayStop(BaseModel):
    poiId: str
    startTime: str
    endTime: str
    reason: str


class ItineraryDay(BaseModel):
    dayNumber: int
    date: str
    theme: str
    summary: str
    stops: list[DayStop]
    routeSegments: list[RouteSegment]


class TravelerProfile(BaseModel):
    pace: Literal["relaxed", "moderate", "intensive"]
    interests: list[str]
    transportPreference: str
    budgetLevel: Literal["low", "medium", "high"]
    partyType: str


class DateRange(BaseModel):
    start: str
    end: str


class ItineraryMap(BaseModel):
    pois: list[MapPoi]


class ValidationResult(BaseModel):
    status: Literal["passed", "warning", "failed"]
    warnings: list[str] = Field(default_factory=list)


class PlannerTrace(BaseModel):
    provider: Literal["mock", "qwen", "doubao"]
    model: str
    generatedAt: str


class ItineraryVersion(BaseModel):
    id: str
    itineraryId: str
    versionNumber: int
    title: str
    city: str
    dateRange: DateRange
    travelerProfile: TravelerProfile
    days: list[ItineraryDay]
    map: ItineraryMap
    validation: ValidationResult
    plannerTrace: PlannerTrace
