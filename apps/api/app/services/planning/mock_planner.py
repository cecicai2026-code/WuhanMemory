from __future__ import annotations

import json
from pathlib import Path

from app.schemas.itinerary import ItineraryVersion


def _project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "packages" / "shared" / "data" / "wuhan-three-day-itinerary.json").exists():
            return parent
    raise RuntimeError("Could not locate project root")


def load_mock_itinerary() -> ItineraryVersion:
    data_path = _project_root() / "packages" / "shared" / "data" / "wuhan-three-day-itinerary.json"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    return ItineraryVersion.model_validate(payload)
