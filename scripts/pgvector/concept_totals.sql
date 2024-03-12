CREATE VIEW concept_totals AS
WITH RECURSIVE concept_children AS (
  SELECT
    r1.id AS concept_id,
    r2.type,
    r2.id AS child_id
  FROM
    reckoning r1
  LEFT JOIN reckoning r2 ON r1.id = r2.parent_reckoning_id
  WHERE
    r1.type = 0 -- Concept
  AND r2.type <> 4 -- Exclude drafts
  UNION ALL
  SELECT
    cc.concept_id,
    r.type,
    r.id
  FROM
    concept_children cc
  JOIN reckoning r ON cc.child_id = r.parent_reckoning_id
  WHERE
    r.type IN (1, 2, 3) -- Supports, Detracts, Points of Order
)
SELECT
  concept_id,
  COUNT(*) FILTER (WHERE type = 5) AS up_votes,
  COUNT(*) FILTER (WHERE type = 6) AS down_votes,
  COUNT(*) FILTER (WHERE type = 1) AS supports,
  COUNT(*) FILTER (WHERE type = 2) AS detracts,
  COUNT(*) FILTER (WHERE type = 3) AS points_of_order
FROM
  concept_children
GROUP BY
  concept_id
ORDER BY
  concept_id;