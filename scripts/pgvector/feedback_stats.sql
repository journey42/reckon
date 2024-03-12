CREATE VIEW feedback_stats AS
SELECT 
    type,
    COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE) AS feedbacks_today,
    COUNT(*) FILTER (WHERE DATE_TRUNC('week', created_at) = DATE_TRUNC('week', CURRENT_DATE)) AS feedbacks_this_week,
    COUNT(*) FILTER (WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE)) AS feedbacks_this_month,
    COUNT(*) FILTER (WHERE DATE_TRUNC('year', created_at) = DATE_TRUNC('year', CURRENT_DATE)) AS feedbacks_this_year,
    COUNT(*) FILTER (WHERE DATE(created_at) = CURRENT_DATE)::float AS avg_per_day,
    (COUNT(*) FILTER (WHERE DATE_TRUNC('week', created_at) = DATE_TRUNC('week', CURRENT_DATE))::float / GREATEST(EXTRACT(DOW FROM CURRENT_DATE) + 1, 1)) AS avg_per_week,
    (COUNT(*) FILTER (WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', CURRENT_DATE))::float / EXTRACT(DAY FROM CURRENT_DATE)) AS avg_per_month,
    (COUNT(*) FILTER (WHERE DATE_TRUNC('year', created_at) = DATE_TRUNC('year', CURRENT_DATE))::float / EXTRACT(DOY FROM CURRENT_DATE)) AS avg_per_year
FROM 
    feedback
GROUP BY 
    type;
