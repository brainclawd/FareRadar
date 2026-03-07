-- FareRadar v1 logical schema reference

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email VARCHAR(255) UNIQUE NOT NULL,
  plan VARCHAR(50) NOT NULL DEFAULT 'free',
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE user_search_preferences (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  origin_airports TEXT[] NOT NULL,
  destination_type VARCHAR(32) NOT NULL,
  destinations TEXT[] NOT NULL DEFAULT '{}',
  max_price INTEGER NOT NULL,
  cabin_class VARCHAR(32) NOT NULL,
  date_flexibility VARCHAR(32) NOT NULL DEFAULT 'exact',
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE user_alerts (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name VARCHAR(120) NOT NULL,
  origin_airports TEXT[] NOT NULL,
  destination_type VARCHAR(32) NOT NULL,
  destinations TEXT[] NOT NULL DEFAULT '{}',
  max_price INTEGER NULL,
  cabin_class VARCHAR(32) NOT NULL,
  date_flexibility VARCHAR(32) NOT NULL DEFAULT 'exact',
  min_discount_percent FLOAT NOT NULL DEFAULT 35,
  channels TEXT[] NOT NULL DEFAULT '{"email"}',
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE route_buckets (
  id SERIAL PRIMARY KEY,
  origin VARCHAR(8) NOT NULL,
  destination VARCHAR(8) NOT NULL,
  cabin_class VARCHAR(32) NOT NULL,
  departure_month VARCHAR(7) NOT NULL,
  trip_length_min INTEGER NOT NULL,
  trip_length_max INTEGER NOT NULL,
  priority_score FLOAT NOT NULL DEFAULT 0,
  demand_score FLOAT NOT NULL DEFAULT 1,
  volatility_score FLOAT NOT NULL DEFAULT 1,
  deal_frequency_score FLOAT NOT NULL DEFAULT 1,
  refresh_interval_minutes INTEGER NOT NULL DEFAULT 60,
  last_scanned_at TIMESTAMP NULL,
  next_scan_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE(origin, destination, cabin_class, departure_month, trip_length_min, trip_length_max)
);

CREATE TABLE scan_jobs (
  id SERIAL PRIMARY KEY,
  provider VARCHAR(32) NOT NULL,
  origin VARCHAR(8) NOT NULL,
  destination VARCHAR(8) NOT NULL,
  cabin_class VARCHAR(32) NOT NULL,
  departure_start DATE NOT NULL,
  departure_end DATE NOT NULL,
  trip_length_min INTEGER NOT NULL,
  trip_length_max INTEGER NOT NULL,
  priority_score FLOAT NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'queued',
  error_message TEXT NULL,
  queued_at TIMESTAMP NOT NULL DEFAULT NOW(),
  started_at TIMESTAMP NULL,
  completed_at TIMESTAMP NULL
);

CREATE TABLE flight_prices (
  id SERIAL PRIMARY KEY,
  provider VARCHAR(32) NOT NULL DEFAULT 'mock',
  origin VARCHAR(8) NOT NULL,
  destination VARCHAR(8) NOT NULL,
  departure_date DATE NOT NULL,
  return_date DATE NOT NULL,
  airline VARCHAR(64) NOT NULL,
  cabin_class VARCHAR(32) NOT NULL,
  stops INTEGER NOT NULL DEFAULT 0,
  price INTEGER NOT NULL,
  currency_code VARCHAR(3) NOT NULL DEFAULT 'USD',
  deep_link TEXT NULL,
  fidelity_score FLOAT NOT NULL DEFAULT 0.9,
  raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  observed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_flight_prices_route ON flight_prices(origin, destination, cabin_class, observed_at DESC);

CREATE TABLE route_price_stats (
  id SERIAL PRIMARY KEY,
  origin VARCHAR(8) NOT NULL,
  destination VARCHAR(8) NOT NULL,
  cabin_class VARCHAR(32) NOT NULL,
  avg_price FLOAT NOT NULL,
  median_price FLOAT NOT NULL,
  min_price INTEGER NOT NULL,
  max_price INTEGER NOT NULL,
  sample_size INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
  UNIQUE(origin, destination, cabin_class)
);

CREATE TABLE candidate_deals (
  id SERIAL PRIMARY KEY,
  flight_price_id INTEGER NOT NULL UNIQUE REFERENCES flight_prices(id) ON DELETE CASCADE,
  origin VARCHAR(8) NOT NULL,
  destination VARCHAR(8) NOT NULL,
  departure_date DATE NOT NULL,
  return_date DATE NOT NULL,
  airline VARCHAR(64) NOT NULL,
  cabin_class VARCHAR(32) NOT NULL,
  price INTEGER NOT NULL,
  expected_price INTEGER NOT NULL,
  discount_percent FLOAT NOT NULL,
  z_score FLOAT NOT NULL DEFAULT 0,
  sudden_drop_amount INTEGER NOT NULL DEFAULT 0,
  rarity_score FLOAT NOT NULL DEFAULT 0,
  score FLOAT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'candidate',
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE detected_deals (
  id SERIAL PRIMARY KEY,
  candidate_deal_id INTEGER NULL REFERENCES candidate_deals(id) ON DELETE SET NULL,
  origin VARCHAR(8) NOT NULL,
  destination VARCHAR(8) NOT NULL,
  price INTEGER NOT NULL,
  normal_price INTEGER NOT NULL,
  discount_percent FLOAT NOT NULL,
  airline VARCHAR(64) NOT NULL,
  departure_date DATE NOT NULL,
  return_date DATE NOT NULL,
  cabin_class VARCHAR(32) NOT NULL,
  provider VARCHAR(32) NOT NULL DEFAULT 'mock',
  deep_link TEXT NULL,
  deal_score FLOAT NOT NULL DEFAULT 0,
  status VARCHAR(32) NOT NULL DEFAULT 'validated',
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE deal_alerts (
  id SERIAL PRIMARY KEY,
  user_alert_id INTEGER NOT NULL REFERENCES user_alerts(id) ON DELETE CASCADE,
  deal_id INTEGER NOT NULL REFERENCES detected_deals(id) ON DELETE CASCADE,
  channel VARCHAR(16) NOT NULL DEFAULT 'email',
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  queued_at TIMESTAMP NOT NULL DEFAULT NOW(),
  sent_at TIMESTAMP NULL,
  UNIQUE(user_alert_id, deal_id)
);

CREATE TABLE notifications (
  id SERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  deal_id INTEGER NOT NULL REFERENCES detected_deals(id) ON DELETE CASCADE,
  channel VARCHAR(32) NOT NULL DEFAULT 'email',
  sent_at TIMESTAMP NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);


ALTER TABLE detected_deals
  ADD COLUMN IF NOT EXISTS feed_score FLOAT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS quality_factors_json JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS provider_health_events (
  id SERIAL PRIMARY KEY,
  provider VARCHAR(32) NOT NULL,
  status VARCHAR(16) NOT NULL,
  operation VARCHAR(32) NOT NULL DEFAULT 'search',
  latency_ms INTEGER NULL,
  error_message TEXT NULL,
  context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provider_health_provider_created_at
  ON provider_health_events(provider, created_at DESC);
