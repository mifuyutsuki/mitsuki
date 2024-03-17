BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS "gacha_settings" (
    "rarity"	INTEGER NOT NULL,
    "rate"	FLOAT NOT NULL,
    "dupe_shards"	INTEGER NOT NULL,
    "color"	INTEGER NOT NULL,
    "stars"	VARCHAR NOT NULL,
    "pity"	INTEGER,
    PRIMARY KEY("rarity")
);

CREATE TABLE IF NOT EXISTS "gacha_pity2" (
    "user"	INTEGER NOT NULL,
    "rarity"	INTEGER NOT NULL,
    "count"	INTEGER NOT NULL,
    PRIMARY KEY("user","rarity")
    -- FOREIGN KEY("rarity") REFERENCES "gacha_settings"("rarity")
);

CREATE TABLE IF NOT EXISTS "gacha_cards" (
    "id"	VARCHAR NOT NULL,
    "name"	VARCHAR NOT NULL,
    "rarity"	INTEGER NOT NULL,
    "type"	VARCHAR NOT NULL,
    "series"	VARCHAR NOT NULL,
    "image"	VARCHAR,
    PRIMARY KEY("id"),
    FOREIGN KEY("rarity") REFERENCES "gacha_settings"("rarity")
);

ALTER TABLE "gacha_currency" ADD COLUMN "first_daily" FLOAT;

CREATE TABLE IF NOT EXISTS "new_gacha_inventory" (
    "user"	INTEGER NOT NULL,
    "card"	VARCHAR NOT NULL,
    "count"	INTEGER NOT NULL,
    "first_acquired"	FLOAT,
    -- FOREIGN KEY("card") REFERENCES "gacha_cards"("id"),
    PRIMARY KEY("user","card")
);

INSERT INTO "new_gacha_inventory"
    ("user", "card", "count", "first_acquired")
SELECT
    "user", "card", "count", "first_acquired"
FROM "gacha_inventory";

DROP TABLE "gacha_inventory";
ALTER TABLE "new_gacha_inventory" RENAME TO "gacha_inventory";


CREATE TABLE IF NOT EXISTS "new_gacha_rolls" (
    "id"	INTEGER NOT NULL,
    "user"	INTEGER NOT NULL,
    "card"	VARCHAR NOT NULL,
    "time"	FLOAT NOT NULL,
    PRIMARY KEY("id")
    -- FOREIGN KEY("card") REFERENCES "gacha_cards"("id")
);

INSERT INTO "new_gacha_rolls"
    ("id", "user", "card", "time")
SELECT
    "id", "user", "card", "time"
FROM "gacha_rolls";

DROP TABLE "gacha_rolls";
ALTER TABLE "new_gacha_rolls" RENAME TO "gacha_rolls";

INSERT INTO "gacha_pity2"
  ("user", "rarity", "count")
SELECT
  "user", 2, "counter2"
FROM "gacha_pity"
UNION SELECT
  "user", 3, "counter3"
FROM "gacha_pity"
UNION SELECT
  "user", 4, "counter4"
FROM "gacha_pity";

COMMIT;
