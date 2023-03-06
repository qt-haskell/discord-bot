CREATE TABLE IF NOT EXISTS guilds (
    gid BIGINT PRIMARY KEY NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (now() AT TIME ZONE 'UTC') NOT NULL,
    owo_prefix TEXT NOT NULL DEFAULT 'owo',
    owo_counting BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT guilds_gid_check CHECK (gid > 0)
);

CREATE TABLE IF NOT EXISTS guild_prefixes (
    id BIGSERIAL PRIMARY KEY NOT NULL,
    gid BIGINT NOT NULL,
    prefix TEXT NOT NULL,
    CONSTRAINT guild_prefixes_gid_fk FOREIGN KEY (gid) REFERENCES guilds(gid) ON DELETE CASCADE,
    CONSTRAINT guild_prefixes_prefix_pk UNIQUE (gid, prefix),
    CONSTRAINT guild_prefixex_prefix_empty_check CHECK (prefix <> '')
);

CREATE OR REPLACE FUNCTION insert_default_prefix()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM guild_prefixes WHERE gid = NEW.gid) THEN
        INSERT INTO guild_prefixes (gid, prefix) VALUES (NEW.gid, 'pls');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;


DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'insert_default_prefix') THEN
        CREATE TRIGGER insert_default_prefix
        AFTER INSERT ON guilds
        FOR EACH ROW EXECUTE PROCEDURE insert_default_prefix();
    END IF;
END;
$$;
