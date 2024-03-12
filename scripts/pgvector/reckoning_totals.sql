CREATE VIEW reckoning_totals AS
SELECT
  CASE
    WHEN type = 0 THEN 'concept'
    WHEN type = 1 THEN 'supports'
    WHEN type = 2 THEN 'detracts'
    WHEN type = 3 THEN 'point_of_order'
    WHEN type = 4 THEN 'draft'
    WHEN type = 5 THEN 'up_vote'
    WHEN type = 6 THEN 'down_vote'
    ELSE 'unknown'
  END AS reckoning_type,
  COUNT(*) AS total
FROM
  reckoning
GROUP BY
  type;
