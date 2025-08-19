-- Mitsuki SQLite database migration from v4.x to v5.0.

BEGIN TRANSACTION;

-- Note: for SQLite, INTEGER and BIGINT are the same, so no action is needed on
-- these columns in this migration.

-- ---------------------------
-- CardRarity [gacha_settings]

ALTER TABLE "gacha_settings" ADD COLUMN "emoji" VARCHAR;

COMMIT;