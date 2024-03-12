CREATE OR REPLACE PROCEDURE aggregate_concept_data_recursive()
LANGUAGE plpgsql
AS $$
BEGIN
    -- Truncate the result table to remove old data
    TRUNCATE TABLE concept_stats;
    
    WITH RECURSIVE rec_agg AS (
        -- Select all concepts
        SELECT
            r.id AS concept_id,
            r.id AS reckoning_id,
            r.type,
            0 AS depth -- Starting depth for concepts
        FROM
            reckoning r
        WHERE
            r.type = 0 -- Concept type
        UNION ALL
        -- Recursively select children, avoiding double counting by not reselecting concepts
        SELECT
            ra.concept_id, -- Preserve the original concept_id through recursion
            r.id,
            r.type,
            ra.depth + 1
        FROM
            reckoning r
        JOIN rec_agg ra ON r.parent_reckoning_id = ra.reckoning_id
        WHERE
            r.type <> 4 -- Exclude drafts
    ),
    filtered_agg AS (
        SELECT
            concept_id,
            type,
            COUNT(*) AS count
        FROM
            rec_agg
        WHERE
            depth > 0 -- Exclude the concept itself from the counts
        GROUP BY
            concept_id, type
    )
    INSERT INTO concept_stats (concept_id, supports, detracts, points_of_order, up_votes, down_votes)
    SELECT
        concept_id,
        COALESCE(SUM(count) FILTER (WHERE type = 5), 0) AS up_votes,
        COALESCE(SUM(count) FILTER (WHERE type = 6), 0) AS down_votes,
        COALESCE(SUM(count) FILTER (WHERE type = 1), 0) AS supports,
        COALESCE(SUM(count) FILTER (WHERE type = 2), 0) AS detracts,
        COALESCE(SUM(count) FILTER (WHERE type = 3), 0) AS points_of_order
    FROM
        filtered_agg
    GROUP BY
        concept_id;
END;
$$;
