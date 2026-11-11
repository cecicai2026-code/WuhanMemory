CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS pois (
  id uuid PRIMARY KEY,
  external_provider text NOT NULL,
  external_id text NOT NULL,
  name text NOT NULL,
  city text NOT NULL,
  district text,
  category text NOT NULL,
  tags text[] NOT NULL DEFAULT '{}',
  location geography(Point, 4326) NOT NULL,
  source_url text,
  last_verified_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS pois_location_gix ON pois USING gist (location);
CREATE INDEX IF NOT EXISTS pois_city_category_idx ON pois (city, category);
CREATE INDEX IF NOT EXISTS pois_tags_gin ON pois USING gin (tags);

CREATE TABLE IF NOT EXISTS itinerary_versions (
  id uuid PRIMARY KEY,
  itinerary_id uuid NOT NULL,
  version_number integer NOT NULL,
  status text NOT NULL,
  planner_provider text NOT NULL,
  planner_model text NOT NULL,
  preference_snapshot jsonb NOT NULL,
  itinerary_json jsonb NOT NULL,
  validation_result jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS share_pages (
  id uuid PRIMARY KEY,
  itinerary_version_id uuid NOT NULL,
  slug text NOT NULL UNIQUE,
  visibility text NOT NULL,
  expires_at timestamptz,
  revoked_at timestamptz,
  view_count integer NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);
