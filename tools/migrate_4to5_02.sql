-- Mitsuki SQLite database migration from v4.x to v5.0.
-- Migration from 4to5_01 to 4to5_02.

BEGIN TRANSACTION;

-- Note: for SQLite, INTEGER and BIGINT are the same, so no action is needed on
-- these columns in this migration.

-- ---------------------------
-- GachaSeason [gacha_seasons]

-- Due to breaking change of adding non-nullable start_time, gacha_seasons is
-- recreated from scratch; old gacha_seasons is removed.

CREATE TABLE "new_gacha_seasons" (
	"id" VARCHAR NOT NULL, 
	"name" VARCHAR NOT NULL, 
	"description" VARCHAR, 
  "image" VARCHAR,
	"collection" VARCHAR NOT NULL, 
	"pickup_rate" FLOAT NOT NULL, 
  "start_time" FLOAT NOT NULL, 
	"end_time" FLOAT NOT NULL, 
	PRIMARY KEY ("id"), 
	FOREIGN KEY ("collection") REFERENCES "gacha_collections" ("id")
);

DROP TABLE "gacha_seasons";
ALTER TABLE "new_gacha_seasons" RENAME TO "gacha_seasons";

-- ------------------
-- Card [gacha_cards]

ALTER TABLE "gacha_cards" ADD COLUMN "limited" BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE "gacha_cards" ADD COLUMN "locked" BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE "gacha_cards" ADD COLUMN "unlisted" BOOLEAN NOT NULL DEFAULT FALSE;

-- ----------------------------------
-- CardCollection [gacha_collections]

ALTER TABLE "gacha_collections" DROP COLUMN "roll_cost";

-- -----------------------
-- [gacha_collection_card]

CREATE TABLE new_gacha_collection_cards (
	"collection" VARCHAR NOT NULL, 
	"card" VARCHAR NOT NULL, 
	PRIMARY KEY ("collection", "card"), 
	FOREIGN KEY ("collection") REFERENCES "gacha_collections" ("id") ON DELETE CASCADE ON UPDATE CASCADE, 
	FOREIGN KEY ("card") REFERENCES "gacha_cards" ("id") ON DELETE CASCADE ON UPDATE CASCADE
)

DROP TABLE "gacha_collection_cards";
ALTER TABLE "new_gacha_collection_cards" RENAME TO "gacha_collection_cards";

COMMIT;