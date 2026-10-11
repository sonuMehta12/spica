-- vector  : embeddings live beside the rows they belong to, so "ask" can filter
--           by tag and join to the ledger in one query instead of keeping a
--           second database in sync (spec/backend.md).
-- pg_trgm : fuzzy text matching — payee names arrive misspelt and truncated.
-- unaccent: normalising those names before matching them.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
