CREATE TABLE IF NOT EXISTS concept_stats (
    concept_id INT PRIMARY KEY,
    supports INT,
    detracts INT,
    points_of_order INT,
    up_votes INT,
    down_votes INT
);