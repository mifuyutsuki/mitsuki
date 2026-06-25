-- Mitsuki SQLite database migration from v4.x to v5.0.

BEGIN TRANSACTION;

-- Note: for SQLite, INTEGER and BIGINT are the same, so no action is needed on
-- these columns in this migration.

-- ---------------------------
-- CardRarity [gacha_settings]

ALTER TABLE "gacha_settings" ADD COLUMN "emoji" VARCHAR;

-- ---------------------------
-- UserPity [gacha_pity2]

-- Some users from before v2.0 may not have a corresponding UserPity entry.

INSERT INTO "gacha_pity2"
  ("user", "rarity", "count")
SELECT
  "user", "rarity", 0 "count"
FROM "gacha_currency", "gacha_settings"
WHERE "pity" > 1
ORDER BY "user", "rarity"
ON CONFLICT DO NOTHING;

-- -----------------------
-- GachaRoll [gacha_rolls]

ALTER TABLE "gacha_rolls" ADD COLUMN "pity_excluded" BOOLEAN DEFAULT FALSE;
ALTER TABLE "gacha_rolls" ADD COLUMN "collection" VARCHAR;

COMMIT;