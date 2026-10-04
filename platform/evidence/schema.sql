-- Evidence index: one row per check and per decision, pointing at the signed
-- bundle in the write-once bucket. Metrics and reports query this table.
CREATE TABLE IF NOT EXISTS evidence (
  id            BIGSERIAL PRIMARY KEY,
  repo          TEXT        NOT NULL,
  main_sha      TEXT        NOT NULL,
  pr            INTEGER,
  pr_head       TEXT,
  check_name    TEXT        NOT NULL,  -- a check, or 'admission' for the decision
  status        TEXT        NOT NULL,  -- pass, fail, skipped, allowed, blocked
  details       TEXT,
  tier          TEXT,
  tree_match    BOOLEAN,
  bundle_uri    TEXT,                  -- where the signed bundle is stored
  collected_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (repo, main_sha, check_name)
);
CREATE INDEX IF NOT EXISTS evidence_by_check ON evidence (check_name, collected_at);
CREATE INDEX IF NOT EXISTS evidence_by_pr ON evidence (repo, pr);
