-- Replace only the derived error-report view, preserving all stored rows.
BEGIN IMMEDIATE;
DROP VIEW IF EXISTS skill_errors;
CREATE VIEW IF NOT EXISTS skill_errors AS
WITH distinct_errors AS (
  SELECT
    skill_name,
    error_message,
    COUNT(*) as error_count,
    MAX(executed_at) as last_error
  FROM skill_executions
  WHERE success = 0
  GROUP BY skill_name, error_message
)
SELECT
  skill_name,
  SUM(error_count) as error_count,
  MAX(last_error) as last_error,
  GROUP_CONCAT(error_message, ' | ') as error_messages
FROM distinct_errors
GROUP BY skill_name
ORDER BY error_count DESC;

-- Force SQLite to prepare the view before the caller commits.
SELECT * FROM skill_errors LIMIT 0;
