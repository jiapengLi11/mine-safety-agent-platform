CREATE TABLE detection_events (
    id BIGINT NOT NULL AUTO_INCREMENT,
    event_id VARCHAR(64) NOT NULL,
    schema_version INT NOT NULL,
    trace_id VARCHAR(64) NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    frame_id BIGINT NOT NULL,
    captured_at TIMESTAMP(6) NOT NULL,
    inferred_at TIMESTAMP(6) NOT NULL,
    model_version VARCHAR(128) NOT NULL,
    payload JSON NOT NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_detection_event_id (event_id),
    KEY idx_detection_camera_time (camera_id, captured_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE alerts (
    id BIGINT NOT NULL AUTO_INCREMENT,
    alert_no VARCHAR(64) NOT NULL,
    rule_id VARCHAR(64) NOT NULL,
    camera_id VARCHAR(64) NOT NULL,
    class_name VARCHAR(64) NOT NULL,
    risk_level VARCHAR(16) NOT NULL,
    state VARCHAR(32) NOT NULL,
    first_seen_at TIMESTAMP(6) NOT NULL,
    last_seen_at TIMESTAMP(6) NOT NULL,
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    UNIQUE KEY uk_alert_no (alert_no),
    KEY idx_alert_camera_state_time (camera_id, state, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE outbox_events (
    id BIGINT NOT NULL AUTO_INCREMENT,
    event_id VARCHAR(64) NOT NULL,
    aggregate_type VARCHAR(64) NOT NULL,
    aggregate_id VARCHAR(64) NOT NULL,
    topic VARCHAR(160) NOT NULL,
    event_key VARCHAR(128) NOT NULL,
    payload JSON NOT NULL,
    status VARCHAR(24) NOT NULL,
    retry_count INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMP(6) NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    published_at TIMESTAMP(6) NULL,
    PRIMARY KEY (id),
    UNIQUE KEY uk_outbox_event_id (event_id),
    KEY idx_outbox_status_attempt (status, next_attempt_at, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE audit_logs (
    id BIGINT NOT NULL AUTO_INCREMENT,
    trace_id VARCHAR(64) NOT NULL,
    actor VARCHAR(128) NOT NULL,
    action VARCHAR(96) NOT NULL,
    resource_type VARCHAR(64) NOT NULL,
    resource_id VARCHAR(128) NOT NULL,
    details JSON NULL,
    created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    PRIMARY KEY (id),
    KEY idx_audit_trace (trace_id),
    KEY idx_audit_resource (resource_type, resource_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
