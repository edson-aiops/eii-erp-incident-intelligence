-- A26 — Audit log de reversões de token_map (PostgreSQL)
-- Registra SOMENTE metadados (nunca o valor real do token) — LGPD art. 12.

CREATE TABLE IF NOT EXISTS tokenmap_audit (
    id BIGSERIAL PRIMARY KEY,
    incident_id VARCHAR(36) NOT NULL,
    job_id VARCHAR(36),
    token_name VARCHAR(50) NOT NULL,
    token_value_length INT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source VARCHAR(50),
    result VARCHAR(20) NOT NULL,
    error_msg TEXT
);

CREATE INDEX IF NOT EXISTS idx_tokenmap_audit_incident_timestamp
    ON tokenmap_audit (incident_id, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_tokenmap_audit_timestamp
    ON tokenmap_audit (timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_tokenmap_audit_result
    ON tokenmap_audit (result);
