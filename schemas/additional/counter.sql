CREATE TABLE IF NOT EXISTS counter (
    counter_id BIGSERIAL PRIMARY KEY NOT NULL,
    counter TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT (now() AT TIME ZONE 'UTC') NOT NULL,
    CONSTRAINT counter_check CHECK (counter ~ '^[a-zA-Z0-9]+$')
);
