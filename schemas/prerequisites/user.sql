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

CREATE OR REPLACE FUNCTION get_score_counts(p_uid BIGINT) RETURNS TABLE (
  daily_score INTEGER,
  yesterday_score INTEGER,
  weekly_score INTEGER,
  last_week_score INTEGER,
  this_week_score INTEGER,
  last_month_score INTEGER,
  this_month_score INTEGER
) AS $$
DECLARE
  time_ranges CONSTANT INTERVAL[] := ARRAY[
    '8 hours'::INTERVAL, '1 day 8 hours'::INTERVAL, '1 week'::INTERVAL,
    '2 weeks'::INTERVAL, '1 week'::INTERVAL, '1 month'::INTERVAL, '2 months'::INTERVAL
  ];
  score_counts INTEGER[];
  i INTEGER;
  start_date TIMESTAMP WITH TIME ZONE;
  end_date TIMESTAMP WITH TIME ZONE;
BEGIN
  -- Fixed length array
  FOR i IN 1..ARRAY_LENGTH(time_ranges, 1) LOOP
    score_counts[i] := 0;
  END LOOP;

  FOR i IN 1..ARRAY_LENGTH(time_ranges, 1) LOOP
    IF now()::TIME < '08:00:00' THEN
      -- If it's before 8am, we subtract an additional day from the start date
      start_date := now()::DATE - '1 day'::INTERVAL + '8 hours'::INTERVAL - time_ranges[i];
    ELSE
      start_date := now()::DATE + '8 hours'::INTERVAL - time_ranges[i];
    END IF;
    end_date := start_date + time_ranges[i-1];
    SELECT
      SUM(CASE WHEN created_at >= start_date AND created_at < end_date THEN 1 ELSE 0 END)
    FROM owo_counting JOIN users ON owo_counting.uid = users.uid
    WHERE uid = p_uid
    INTO score_counts[i];
    END LOOP;

    RETURN QUERY SELECT * FROM score_counts;
END;
$$ LANGUAGE plpgsql;

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
