CREATE VIEW concept_stats AS
WITH RECURSIVE reckoning_tree AS (
  -- Base case: Select all concepts
  SELECT id, type, parent_reckoning_id, CAST(1 AS DOUBLE PRECISION) AS depth -- Cast depth to double precision
  FROM reckoning
  WHERE type = 0 -- Concept
  
  UNION ALL
  
  -- Recursive step: Select children of the current reckoning, excluding drafts
  SELECT r.id, r.type, r.parent_reckoning_id, rt.depth + CAST(1 AS DOUBLE PRECISION) -- Increment depth as double precision
  FROM reckoning r
  INNER JOIN reckoning_tree rt ON r.parent_reckoning_id = rt.id
  WHERE r.type != 4 -- Exclude drafts
),
aggregated_data AS (
  -- Aggregate data across all levels, but treat top-level concepts separately
  SELECT
    CASE WHEN depth = CAST(1 AS DOUBLE PRECISION) THEN NULL ELSE parent_reckoning_id END AS concept_id,
    AVG(CASE WHEN type = 1 THEN CAST(1 AS DOUBLE PRECISION) ELSE CAST(0 AS DOUBLE PRECISION) END) AS avg_supports, -- Cast to double
    AVG(CASE WHEN type = 2 THEN CAST(1 AS DOUBLE PRECISION) ELSE CAST(0 AS DOUBLE PRECISION) END) AS avg_detracts, -- Cast to double
    AVG(CASE WHEN type = 3 THEN CAST(1 AS DOUBLE PRECISION) ELSE CAST(0 AS DOUBLE PRECISION) END) AS avg_points_of_order, -- Cast to double
    AVG(CASE WHEN type = 5 THEN CAST(1 AS DOUBLE PRECISION) ELSE CAST(0 AS DOUBLE PRECISION) END) AS avg_up_votes, -- Cast to double
    AVG(CASE WHEN type = 6 THEN CAST(1 AS DOUBLE PRECISION) ELSE CAST(0 AS DOUBLE PRECISION) END) AS avg_down_votes, -- Cast to double
    AVG(CASE WHEN type IN (1, 2, 3) THEN CAST(1 AS DOUBLE PRECISION) ELSE CAST(0 AS DOUBLE PRECISION) END) AS avg_comments -- Cast to double
  FROM reckoning_tree
  GROUP BY concept_id
)
SELECT
  AVG(avg_up_votes) AS avg_up_votes,
  AVG(avg_down_votes) AS avg_down_votes,
  AVG(avg_comments) AS avg_comments,
  AVG(avg_supports) AS avg_supports,
  AVG(avg_detracts) AS avg_detracts,
  AVG(avg_points_of_order) AS avg_points_of_order
FROM aggregated_data
WHERE concept_id IS NOT NULL; -- Exclude the top-level concepts from final aggregation
