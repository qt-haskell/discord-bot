CREATE TABLE IF NOT EXISTS users (
  uid BIGINT PRIMARY KEY NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'UTC') NOT NULL,
  timezone TEXT NOT NULL DEFAULT 'UTC'
);

CREATE TABLE IF NOT EXISTS presence_history (
  id BIGSERIAL PRIMARY KEY NOT NULL,
  uid BIGINT NOT NULL,
  status TEXT NOT NULL,
  changed_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'UTC') NOT NULL,
  CONSTRAINT presence_history_uid_fk FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE
);

CREATE OR REPLACE FUNCTION insert_into_presence_history(p_user_id bigint, p_status text)
RETURNS void AS $$
BEGIN
  -- Ensure the relationship
  INSERT INTO users (uid) VALUES (p_user_id) ON CONFLICT DO NOTHING;
  INSERT INTO presence_history (uid, status) VALUES (p_user_id, p_status);
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS owo_counting (
  id BIGSERIAL PRIMARY KEY NOT NULL,
  uid BIGINT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL,
  word TEXT NOT NULL,
  CONSTRAINT owo_counting_uid_fk FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE,
  CONSTRAINT owo_counting_word_check CHECK (word IN ('hunt', 'battle', 'owo')) 
);

CREATE TABLE IF NOT EXISTS item_history (
    id BIGSERIAL PRIMARY KEY NOT NULL,
    uid BIGINT NOT NULL,
    item_type TEXT NOT NULL,
    item_value TEXT NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'UTC') NOT NULL,
    CONSTRAINT item_history_uid_fk FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE,
    CONSTRAINT item_history_item_type_check CHECK (item_type IN ('avatar', 'discriminator', 'name'))
);

CREATE TABLE IF NOT EXISTS avatar_history (
    id BIGSERIAL PRIMARY KEY NOT NULL,
    uid BIGINT NOT NULL,
    format TEXT NOT NULL,
    avatar BYTEA NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'UTC') NOT NULL,
    CONSTRAINT avatar_history_uid_fk FOREIGN KEY (uid) REFERENCES users(uid) ON DELETE CASCADE
);

CREATE OR REPLACE FUNCTION insert_avatar_history_item(p_user_id bigint, p_format text, p_avatar bytea)
RETURNS void AS $$
BEGIN
    IF NOT EXISTS (
        WITH last_avatar AS (
            SELECT avatar FROM avatar_history
            WHERE uid = p_user_id
            ORDER BY changed_at DESC
            LIMIT 1
        )
        SELECT 1 FROM last_avatar WHERE avatar = p_avatar
    ) THEN
        INSERT INTO avatar_history (uid, format, avatar) VALUES (p_user_id, p_format, p_avatar);
    END IF;
END;
$$ LANGUAGE plpgsql;
