-- EAIB: EVE Alliance Intel Board
-- Run this against your Supabase project to initialize the schema.

-- Intel reports
CREATE TABLE IF NOT EXISTS eaib_intel_reports (
    id          SERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    system_name TEXT,
    region_name TEXT,
    reporter_name TEXT NOT NULL,
    character_name TEXT,
    corporation_name TEXT,
    alliance_name TEXT,
    threat_level TEXT NOT NULL DEFAULT 'medium'
        CHECK (threat_level IN ('low', 'medium', 'high', 'critical')),
    category TEXT NOT NULL DEFAULT 'other'
        CHECK (category IN ('fleet', 'pos', 'structure', 'gank', 'camp', 'cyno', 'spy', 'war', 'other')),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'resolved', 'expired', 'false_positive')),
    description     TEXT,
    raw_text        TEXT,
    ship_type       TEXT,
    pilot_count     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ
);

-- Tags
CREATE TABLE IF NOT EXISTS eaib_tags (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    color       TEXT NOT NULL DEFAULT '#00d4aa',
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Report <-> tag junction
CREATE TABLE IF NOT EXISTS eaib_report_tags (
    report_id   INTEGER NOT NULL REFERENCES eaib_intel_reports(id) ON DELETE CASCADE,
    tag_id      INTEGER NOT NULL REFERENCES eaib_tags(id) ON DELETE CASCADE,
    PRIMARY KEY (report_id, tag_id)
);

-- Comments
CREATE TABLE IF NOT EXISTS eaib_comments (
    id          SERIAL PRIMARY KEY,
    report_id   INTEGER NOT NULL REFERENCES eaib_intel_reports(id) ON DELETE CASCADE,
    author_name TEXT NOT NULL,
    body        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_eaib_reports_system    ON eaib_intel_reports(system_name);
CREATE INDEX IF NOT EXISTS idx_eaib_reports_region    ON eaib_intel_reports(region_name);
CREATE INDEX IF NOT EXISTS idx_eaib_reports_status    ON eaib_intel_reports(status);
CREATE INDEX IF NOT EXISTS idx_eaib_reports_threat    ON eaib_intel_reports(threat_level);
CREATE INDEX IF NOT EXISTS idx_eaib_reports_category  ON eaib_intel_reports(category);
CREATE INDEX IF NOT EXISTS idx_eaib_reports_created   ON eaib_intel_reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_eaib_report_tags_rep   ON eaib_report_tags(report_id);
CREATE INDEX IF NOT EXISTS idx_eaib_comments_report   ON eaib_comments(report_id);

-- Seed default tags
INSERT INTO eaib_tags (name, color, description) VALUES
    ('Hostile Fleet',   '#ef4444', 'Active hostile fleet sighted'),
    ('Capital Ship',    '#f0a020', 'Capital or super-capital sighted'),
    ('Cyno Lit',        '#a855f7', 'Cynosural field activated'),
    ('Gate Camp',       '#ef4444', 'Gate camp in progress'),
    ('Structure Bash',  '#f0a020', 'Structure under attack'),
    ('Spy Suspected',   '#8b5cf6', 'Suspected spy activity'),
    ('Neutral',         '#8892a4', 'Neutral entity, monitoring'),
    ('Blue',            '#00d4aa', 'Blue/friendly confirmed'),
    ('War Target',      '#ef4444', 'Declared war target'),
    ('Eviction',        '#dc2626', 'Corp/alliance eviction in progress')
ON CONFLICT (name) DO NOTHING;
