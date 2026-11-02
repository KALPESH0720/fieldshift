-- Field Shift backend schema draft
-- PostgreSQL + PostGIS. Review constraints, retention, roles and indexes against
-- the selected launch country before applying to any environment.
-- This is a proposed server schema; current Dexie v4 remains a local cache.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS app_users (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone_e164 text NOT NULL CHECK (phone_e164 ~ '^\+[1-9][0-9]{6,14}$'),
    display_name text CHECK (display_name IS NULL OR length(trim(display_name)) BETWEEN 1 AND 120),
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'disabled')),
    country_code char(2) NOT NULL,
    preferred_locale text NOT NULL DEFAULT 'en',
    sms_opt_in_at timestamptz,
    privacy_accepted_at timestamptz,
    last_login_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CHECK (status <> 'active' OR display_name IS NOT NULL)
);
CREATE UNIQUE INDEX IF NOT EXISTS app_users_phone_unique
    ON app_users (phone_e164) WHERE deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS roles (
    code text PRIMARY KEY CHECK (code IN ('farmer', 'extension', 'admin')),
    label text NOT NULL,
    scope text NOT NULL CHECK (scope IN ('global', 'group')),
    permissions jsonb NOT NULL DEFAULT '[]'::jsonb
);

CREATE TABLE IF NOT EXISTS farm_groups (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    country_code char(2),
    state text,
    district text,
    registration_ref text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);

CREATE TABLE IF NOT EXISTS group_memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    group_id uuid NOT NULL REFERENCES farm_groups(id),
    user_id uuid NOT NULL REFERENCES app_users(id),
    membership_role text NOT NULL CHECK (membership_role IN ('owner', 'admin', 'extension', 'member')),
    status text NOT NULL DEFAULT 'invited' CHECK (status IN ('invited', 'active', 'suspended')),
    permissions jsonb NOT NULL DEFAULT '[]'::jsonb,
    joined_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (group_id, user_id)
);
CREATE INDEX IF NOT EXISTS group_memberships_user_status_idx
    ON group_memberships (user_id, status);

CREATE TABLE IF NOT EXISTS user_roles (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id),
    role_code text NOT NULL REFERENCES roles(code),
    group_id uuid REFERENCES farm_groups(id),
    granted_by uuid REFERENCES app_users(id),
    granted_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS user_roles_global_unique
    ON user_roles (user_id, role_code) WHERE group_id IS NULL;
CREATE UNIQUE INDEX IF NOT EXISTS user_roles_group_unique
    ON user_roles (user_id, role_code, group_id) WHERE group_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id uuid PRIMARY KEY REFERENCES app_users(id),
    locale text NOT NULL DEFAULT 'en',
    theme text NOT NULL DEFAULT 'system' CHECK (theme IN ('system', 'light', 'dark')),
    area_unit text,
    temperature_unit text CHECK (temperature_unit IS NULL OR temperature_unit IN ('C', 'F')),
    wind_unit text,
    precipitation_unit text,
    sowing_reminder boolean NOT NULL DEFAULT false,
    fertilizer_reminder boolean NOT NULL DEFAULT false,
    notification_channels text[] NOT NULL DEFAULT '{}',
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crops (
    id text PRIMARY KEY,
    family text NOT NULL,
    emoji text,
    default_season text CHECK (default_season IS NULL OR default_season IN ('Rabi', 'Kharif', 'Zaid')),
    root_depth text CHECK (root_depth IS NULL OR root_depth IN ('shallow', 'medium', 'deep')),
    water_need jsonb,
    thumb_url text,
    card_url text,
    localized_names jsonb NOT NULL DEFAULT '{}'::jsonb,
    active boolean NOT NULL DEFAULT true,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seasons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    code text NOT NULL CHECK (code IN ('Rabi', 'Kharif', 'Zaid')),
    display_name text NOT NULL,
    year integer NOT NULL,
    country_code char(2),
    state_code text,
    starts_on date,
    ends_on date,
    UNIQUE (code, year, country_code, state_code)
);

CREATE TABLE IF NOT EXISTS file_assets (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES app_users(id),
    object_key text NOT NULL UNIQUE,
    purpose text NOT NULL CHECK (purpose IN ('soil-card', 'pest-scan', 'registry-document', 'other')),
    mime_type text NOT NULL CHECK (mime_type IN ('image/jpeg', 'image/png', 'image/webp', 'application/pdf')),
    size_bytes bigint NOT NULL CHECK (size_bytes > 0),
    sha256 text,
    status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'uploaded', 'scanning', 'scanned', 'rejected', 'deleted')),
    virus_scan_status text NOT NULL DEFAULT 'pending' CHECK (virus_scan_status IN ('pending', 'clean', 'infected', 'failed', 'not_required')),
    created_at timestamptz NOT NULL DEFAULT now(),
    scanned_at timestamptz,
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS file_assets_owner_status_idx ON file_assets (owner_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS land_registry_consents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id),
    provider_id text NOT NULL,
    country_code char(2) NOT NULL,
    scopes text[] NOT NULL CHECK (cardinality(scopes) > 0),
    purpose text NOT NULL,
    status text NOT NULL CHECK (status IN ('initiated', 'granted', 'denied', 'revoked', 'expired')),
    provider_consent_ref text,
    notice_version text NOT NULL,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    initiated_at timestamptz NOT NULL DEFAULT now(),
    granted_at timestamptz,
    revoked_at timestamptz,
    expires_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((status <> 'granted') OR granted_at IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS registry_consents_user_provider_idx
    ON land_registry_consents (user_id, provider_id, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS plots (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES app_users(id),
    local_id text,
    name text NOT NULL CHECK (length(trim(name)) BETWEEN 1 AND 120),
    area numeric(14, 6) NOT NULL CHECK (area > 0),
    area_unit text NOT NULL CHECK (area_unit IN ('acre', 'hectare', 'guntha', 'sqm', 'sqft')),
    area_hectares numeric(14, 8) NOT NULL CHECK (area_hectares > 0),
    village text,
    primary_crop_id text REFERENCES crops(id),
    intercrop_id text REFERENCES crops(id),
    boundary geometry(Geometry, 4326),
    is_verified boolean NOT NULL DEFAULT false,
    source text NOT NULL CHECK (source IN ('manual', 'in-agristack', 'provider')),
    provider_id text,
    parcel_ref text,
    external_id text,
    verified_at timestamptz,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    CHECK (boundary IS NULL OR GeometryType(boundary) IN ('POLYGON', 'MULTIPOLYGON')),
    CHECK (boundary IS NULL OR ST_SRID(boundary) = 4326),
    CHECK (NOT is_verified OR (provider_id IS NOT NULL AND verified_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS plots_owner_updated_idx ON plots (owner_id, updated_at DESC) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS plots_owner_village_idx ON plots (owner_id, village) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS plots_boundary_gist_idx ON plots USING gist (boundary);
CREATE UNIQUE INDEX IF NOT EXISTS plots_registry_external_unique
    ON plots (owner_id, provider_id, external_id)
    WHERE provider_id IS NOT NULL AND external_id IS NOT NULL AND deleted_at IS NULL;

CREATE TABLE IF NOT EXISTS land_registry_parcels (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES app_users(id),
    consent_id uuid REFERENCES land_registry_consents(id),
    provider_id text NOT NULL,
    country_code char(2) NOT NULL,
    parcel_ref text NOT NULL,
    external_id text,
    geometry geometry(Geometry, 4326) NOT NULL,
    area_hectares numeric(14, 8),
    land_use text,
    crop_declared text,
    owner_status text CHECK (owner_status IS NULL OR owner_status IN ('owner', 'tenant', 'unknown')),
    source text NOT NULL,
    is_verified boolean NOT NULL DEFAULT false,
    verified_at timestamptz,
    registry_url text,
    raw_provider_ref text,
    imported_plot_id uuid REFERENCES plots(id),
    fetched_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (owner_id, provider_id, parcel_ref),
    CHECK (GeometryType(geometry) IN ('POLYGON', 'MULTIPOLYGON')),
    CHECK (ST_SRID(geometry) = 4326),
    CHECK (NOT is_verified OR verified_at IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS registry_parcels_geometry_gist_idx
    ON land_registry_parcels USING gist (geometry);
CREATE INDEX IF NOT EXISTS registry_parcels_owner_idx
    ON land_registry_parcels (owner_id, provider_id, fetched_at DESC);

CREATE TABLE IF NOT EXISTS plot_seasons (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    plot_id uuid NOT NULL REFERENCES plots(id),
    season_id uuid REFERENCES seasons(id),
    season_code text NOT NULL CHECK (season_code IN ('Rabi', 'Kharif', 'Zaid')),
    year integer NOT NULL,
    crop_id text NOT NULL REFERENCES crops(id),
    previous_crop_id text REFERENCES crops(id),
    status text NOT NULL CHECK (status IN ('planned', 'active', 'harvested', 'cancelled')),
    area_hectares numeric(14, 8),
    source_recommendation_id uuid,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    planned_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz,
    UNIQUE (plot_id, season_code, year)
);

CREATE TABLE IF NOT EXISTS soil_records (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES app_users(id),
    plot_id uuid REFERENCES plots(id),
    asset_id uuid REFERENCES file_assets(id),
    ph numeric(5, 2) CHECK (ph IS NULL OR ph BETWEEN 0 AND 14),
    nitrogen_kg_ha numeric(12, 4) CHECK (nitrogen_kg_ha IS NULL OR nitrogen_kg_ha >= 0),
    phosphorus_kg_ha numeric(12, 4) CHECK (phosphorus_kg_ha IS NULL OR phosphorus_kg_ha >= 0),
    potassium_kg_ha numeric(12, 4) CHECK (potassium_kg_ha IS NULL OR potassium_kg_ha >= 0),
    organic_carbon_pct numeric(8, 4) CHECK (organic_carbon_pct IS NULL OR organic_carbon_pct >= 0),
    ec_ds_m numeric(8, 4) CHECK (ec_ds_m IS NULL OR ec_ds_m >= 0),
    sampled_at timestamptz,
    source text NOT NULL CHECK (source IN ('manual', 'ocr', 'import')),
    ocr_status text CHECK (ocr_status IS NULL OR ocr_status IN ('queued', 'processing', 'done', 'failed')),
    ocr_confidence numeric(4, 3) CHECK (ocr_confidence IS NULL OR ocr_confidence BETWEEN 0 AND 1),
    ocr_result jsonb,
    version integer NOT NULL DEFAULT 1 CHECK (version > 0),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS soil_records_owner_sampled_idx ON soil_records (owner_id, sampled_at DESC);
CREATE INDEX IF NOT EXISTS soil_records_plot_sampled_idx ON soil_records (plot_id, sampled_at DESC);

CREATE TABLE IF NOT EXISTS crop_rules (
    id text PRIMARY KEY,
    crop_id text REFERENCES crops(id),
    crop_family text NOT NULL,
    root_depth text CHECK (root_depth IS NULL OR root_depth IN ('shallow', 'medium', 'deep')),
    seasons text[] NOT NULL,
    duration_days_min integer,
    duration_days_max integer,
    nitrogen_effect numeric(12, 4),
    fertilizer_reduction_per_hectare numeric(12, 4),
    fertilizer_name text,
    water_need jsonb,
    water_savings_pct numeric(5, 2),
    soil_health_score numeric(6, 3),
    base_return_per_hectare numeric(14, 2),
    country_code char(2),
    state_code text,
    conditions jsonb NOT NULL DEFAULT '{}'::jsonb,
    rule_version text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK (duration_days_min IS NULL OR duration_days_min > 0),
    CHECK (duration_days_max IS NULL OR duration_days_max >= duration_days_min)
);

CREATE TABLE IF NOT EXISTS recommendations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES app_users(id),
    plot_id uuid NOT NULL REFERENCES plots(id),
    season_id uuid REFERENCES seasons(id),
    season_code text NOT NULL CHECK (season_code IN ('Rabi', 'Kharif', 'Zaid')),
    season_year integer NOT NULL,
    previous_crop_id text REFERENCES crops(id),
    soil_record_id uuid REFERENCES soil_records(id),
    request_inputs jsonb NOT NULL,
    model_version text NOT NULL,
    status text NOT NULL DEFAULT 'generated' CHECK (status IN ('generated', 'selected', 'expired')),
    selected_crop_id text REFERENCES crops(id),
    generated_at timestamptz NOT NULL DEFAULT now(),
    version integer NOT NULL DEFAULT 1 CHECK (version > 0)
);
CREATE INDEX IF NOT EXISTS recommendations_owner_plot_idx
    ON recommendations (owner_id, plot_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS recommendation_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id uuid NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
    crop_id text NOT NULL REFERENCES crops(id),
    rank integer NOT NULL CHECK (rank > 0),
    score numeric(8, 4),
    reason text NOT NULL,
    estimated_net_return numeric(14, 2),
    currency char(3),
    baseline_return numeric(14, 2),
    fertilizer_reduction_kg numeric(12, 4),
    fertilizer_cost_savings numeric(14, 2),
    water_savings_pct numeric(5, 2),
    item_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (recommendation_id, rank),
    UNIQUE (recommendation_id, crop_id)
);
ALTER TABLE plot_seasons
    DROP CONSTRAINT IF EXISTS plot_seasons_source_recommendation_id_fkey;
ALTER TABLE plot_seasons
    ADD CONSTRAINT plot_seasons_source_recommendation_id_fkey
    FOREIGN KEY (source_recommendation_id) REFERENCES recommendations(id);

CREATE TABLE IF NOT EXISTS pest_scans (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id uuid NOT NULL REFERENCES app_users(id),
    plot_id uuid REFERENCES plots(id),
    asset_id uuid NOT NULL REFERENCES file_assets(id),
    crop_id text REFERENCES crops(id),
    status text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'done', 'failed')),
    disease_code text,
    disease_name text,
    confidence numeric(5, 4) CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    severity text CHECK (severity IS NULL OR severity IN ('low', 'moderate', 'high', 'unknown')),
    description text,
    localized_advice jsonb NOT NULL DEFAULT '{}'::jsonb,
    model_version text,
    reviewed_by uuid REFERENCES app_users(id),
    reviewed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS pest_scans_owner_created_idx ON pest_scans (owner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS pest_scans_plot_created_idx ON pest_scans (plot_id, created_at DESC);

CREATE TABLE IF NOT EXISTS market_prices (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code char(2) NOT NULL,
    state_code text,
    district text,
    market text NOT NULL,
    crop_id text REFERENCES crops(id),
    crop_name text,
    variety text,
    grade text,
    minimum_price numeric(14, 4),
    maximum_price numeric(14, 4),
    modal_price numeric(14, 4),
    unit text NOT NULL,
    currency char(3) NOT NULL,
    observed_on date NOT NULL,
    source text NOT NULL,
    source_record_id text,
    fetched_at timestamptz NOT NULL DEFAULT now(),
    raw_data jsonb NOT NULL DEFAULT '{}'::jsonb,
    CHECK (minimum_price IS NULL OR minimum_price >= 0),
    CHECK (maximum_price IS NULL OR maximum_price >= 0),
    CHECK (modal_price IS NULL OR modal_price >= 0)
);
CREATE INDEX IF NOT EXISTS market_prices_region_date_idx
    ON market_prices (country_code, state_code, district, market, observed_on DESC);
CREATE INDEX IF NOT EXISTS market_prices_crop_date_idx
    ON market_prices (crop_id, observed_on DESC);

CREATE TABLE IF NOT EXISTS schemes (
    id text PRIMARY KEY,
    country_code char(2) NOT NULL,
    name text NOT NULL,
    focus text,
    description text NOT NULL,
    benefit jsonb NOT NULL DEFAULT '{}'::jsonb,
    eligibility_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
    application_url text,
    document_url text,
    source_url text,
    valid_from date,
    valid_to date,
    updated_at timestamptz NOT NULL DEFAULT now(),
    active boolean NOT NULL DEFAULT true
);
CREATE INDEX IF NOT EXISTS schemes_country_active_idx ON schemes (country_code, active, name);

CREATE TABLE IF NOT EXISTS scheme_eligibility_checks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scheme_id text NOT NULL REFERENCES schemes(id),
    user_id uuid NOT NULL REFERENCES app_users(id),
    plot_id uuid REFERENCES plots(id),
    eligible boolean NOT NULL,
    missing_requirements jsonb NOT NULL DEFAULT '[]'::jsonb,
    source_updated_at timestamptz,
    assessed_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS scheme_checks_user_time_idx
    ON scheme_eligibility_checks (user_id, assessed_at DESC);

CREATE TABLE IF NOT EXISTS dealers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    phone text,
    address text,
    country_code char(2),
    state_code text,
    district text,
    village text,
    location geography(Point, 4326),
    source text,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS dealers_location_gist_idx ON dealers USING gist (location);
CREATE INDEX IF NOT EXISTS dealers_region_active_idx
    ON dealers (country_code, state_code, district, active);

CREATE TABLE IF NOT EXISTS dealer_stock (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    dealer_id uuid NOT NULL REFERENCES dealers(id) ON DELETE CASCADE,
    product_id text,
    product_label text NOT NULL,
    availability text NOT NULL CHECK (availability IN ('in_stock', 'low_stock', 'out_of_stock', 'unknown')),
    inventory_updated_at timestamptz,
    source text,
    UNIQUE (dealer_id, product_id, product_label)
);

CREATE TABLE IF NOT EXISTS notifications (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id),
    notification_type text NOT NULL,
    title text NOT NULL CHECK (length(title) <= 120),
    body text NOT NULL CHECK (length(body) <= 2000),
    icon text,
    severity text CHECK (severity IS NULL OR severity IN ('info', 'warning', 'success')),
    locale text,
    related_entity_type text,
    related_entity_id uuid,
    data jsonb NOT NULL DEFAULT '{}'::jsonb,
    delivery_channels text[] NOT NULL DEFAULT '{}',
    created_at timestamptz NOT NULL DEFAULT now(),
    read_at timestamptz,
    dismissed_at timestamptz,
    expires_at timestamptz
);
CREATE INDEX IF NOT EXISTS notifications_user_created_idx
    ON notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS notifications_user_unread_idx
    ON notifications (user_id, created_at DESC) WHERE read_at IS NULL;

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id),
    endpoint text NOT NULL,
    p256dh text NOT NULL,
    auth_secret text NOT NULL,
    user_agent text,
    created_at timestamptz NOT NULL DEFAULT now(),
    last_success_at timestamptz,
    revoked_at timestamptz,
    UNIQUE (user_id, endpoint)
);

CREATE TABLE IF NOT EXISTS weather_cache (
    cache_key text PRIMARY KEY,
    plot_id uuid REFERENCES plots(id) ON DELETE CASCADE,
    location geography(Point, 4326) NOT NULL,
    provider text NOT NULL,
    fetched_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    attribution text,
    schema_version integer NOT NULL DEFAULT 1,
    payload jsonb NOT NULL
);
CREATE INDEX IF NOT EXISTS weather_cache_location_gist_idx ON weather_cache USING gist (location);
CREATE INDEX IF NOT EXISTS weather_cache_expiry_idx ON weather_cache (expires_at);

CREATE TABLE IF NOT EXISTS auth_sessions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id),
    refresh_token_hash text NOT NULL UNIQUE,
    family_id uuid NOT NULL,
    device_id uuid,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    rotated_at timestamptz,
    revoked_at timestamptz,
    ip_hash text,
    user_agent text
);
CREATE INDEX IF NOT EXISTS auth_sessions_user_active_idx
    ON auth_sessions (user_id, expires_at DESC) WHERE revoked_at IS NULL;

-- OTP codes are NEVER stored in plaintext; code_hash is HMAC-SHA256(server_secret, challenge_id || ':' || phone_e164 || ':' || code).
-- Expiry is 5 minutes (300 seconds); max 5 verification attempts per challenge.
CREATE TABLE IF NOT EXISTS otp_challenges (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_hash text NOT NULL,
    purpose text NOT NULL DEFAULT 'login' CHECK (purpose IN ('login')),
    channel text NOT NULL DEFAULT 'sms' CHECK (channel IN ('sms', 'voice')),
    code_hash text NOT NULL,
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts BETWEEN 0 AND 5),
    max_attempts integer NOT NULL DEFAULT 5 CHECK (max_attempts = 5),
    ip_hash text,
    device_id uuid,
    expires_at timestamptz NOT NULL,
    consumed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS otp_challenges_contact_created_idx
    ON otp_challenges (contact_hash, created_at DESC);
CREATE INDEX IF NOT EXISTS otp_challenges_ip_created_idx
    ON otp_challenges (ip_hash, created_at DESC) WHERE ip_hash IS NOT NULL;

-- Device-local queue remains in Dexie. These server tables make replay
-- idempotent and provide an account-scoped pull feed.
CREATE TABLE IF NOT EXISTS sync_mutations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL REFERENCES app_users(id),
    device_id uuid NOT NULL,
    client_mutation_id uuid NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid,
    operation text NOT NULL CHECK (operation IN ('create', 'update', 'delete')),
    request_hash text NOT NULL,
    result jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, client_mutation_id)
);
CREATE INDEX IF NOT EXISTS sync_mutations_user_created_idx
    ON sync_mutations (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS sync_changes (
    cursor bigserial PRIMARY KEY,
    owner_id uuid NOT NULL REFERENCES app_users(id),
    group_id uuid REFERENCES farm_groups(id),
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    operation text NOT NULL CHECK (operation IN ('upsert', 'delete')),
    version integer NOT NULL,
    record jsonb,
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((operation = 'delete') OR record IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS sync_changes_owner_cursor_idx ON sync_changes (owner_id, cursor);
CREATE INDEX IF NOT EXISTS sync_changes_group_cursor_idx ON sync_changes (group_id, cursor);

CREATE TABLE IF NOT EXISTS audit_events (
    id bigserial PRIMARY KEY,
    actor_user_id uuid REFERENCES app_users(id),
    group_id uuid REFERENCES farm_groups(id),
    action text NOT NULL,
    target_type text,
    target_id text,
    request_id text,
    outcome text NOT NULL,
    changed_fields jsonb NOT NULL DEFAULT '[]'::jsonb,
    ip_hash text,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS audit_events_actor_time_idx
    ON audit_events (actor_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS audit_events_target_idx
    ON audit_events (target_type, target_id, created_at DESC);

INSERT INTO roles (code, label, scope, permissions) VALUES
    ('farmer', 'Farmer', 'global', '["plots:own:read","plots:own:write","soil:own:write","recommendations:own:read","recommendations:own:write"]'::jsonb),
    ('extension', 'Extension worker', 'group', '["groups:assigned:read","farmers:assigned:read"]'::jsonb),
    ('admin', 'Administrator', 'global', '["catalog:write","providers:manage","roles:manage","audit:read"]'::jsonb)
ON CONFLICT (code) DO NOTHING;

COMMIT;

-- Dexie migration notes:
-- 1. Preserve local auto-increment id as local_id; map server id to server_id.
-- 2. Convert saved [latitude, longitude] arrays to GeoJSON [longitude, latitude].
-- 3. Convert string area + areaUnit into numeric area and area_hectares.
-- 4. Add ownerId, version, updatedAt, deletedAt, syncState, clientMutationId,
--    attempts, nextAttemptAt, deviceId and attachmentRefs in a Dexie v5 migration.
-- 5. Backfill old source/provenance carefully; never promote a locally set
--    isVerified flag to an authoritative server verification.

