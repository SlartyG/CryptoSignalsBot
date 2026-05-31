-- Analytics views for Metabase (run after migrations)

CREATE OR REPLACE VIEW v_signals_daily AS
SELECT date_trunc('day', created_at) AS day,
       type,
       symbol,
       confidence,
       count(*) AS cnt
FROM signals_log
GROUP BY 1, 2, 3, 4;

CREATE OR REPLACE VIEW v_active_subscribers AS
SELECT count(DISTINCT user_id) AS active_paid
FROM subscriptions
WHERE status = 'active' AND ends_at > now();

CREATE OR REPLACE VIEW v_users_by_tier AS
SELECT count(*) FILTER (WHERE s.user_id IS NOT NULL) AS paid_users,
       count(*) FILTER (WHERE s.user_id IS NULL) AS free_users
FROM users u
LEFT JOIN (
    SELECT DISTINCT user_id
    FROM subscriptions
    WHERE status = 'active' AND ends_at > now()
) s ON s.user_id = u.id
WHERE u.banned = false;

CREATE OR REPLACE VIEW v_mrr_usdt AS
SELECT coalesce(sum(amount_usdt), 0) / 30.0 AS mrr_usdt
FROM payments
WHERE status = 'paid'
  AND paid_at >= now() - interval '30 days';

CREATE OR REPLACE VIEW v_conversion_cohorts AS
SELECT date_trunc('week', u.created_at) AS cohort_week,
       count(*) AS registered,
       count(p.user_id) AS converted
FROM users u
LEFT JOIN (
    SELECT DISTINCT user_id FROM payments WHERE status = 'paid'
) p ON p.user_id = u.id
GROUP BY 1
ORDER BY 1;

CREATE OR REPLACE VIEW v_collector_uptime AS
SELECT collector_name,
       date_trunc('hour', ts) AS hour,
       round(100.0 * avg(CASE WHEN success THEN 1 ELSE 0 END), 2) AS uptime_pct,
       avg(latency_ms) AS avg_latency_ms
FROM collector_metrics
WHERE ts >= now() - interval '7 days'
GROUP BY 1, 2;

CREATE OR REPLACE VIEW v_delivery_latency_by_priority AS
SELECT d.priority,
       avg(extract(epoch FROM (d.sent_at - s.created_at))) AS avg_delay_sec,
       count(*) AS deliveries
FROM delivery_log d
JOIN signals_log s ON s.id = d.signal_id
WHERE d.sent_at IS NOT NULL
  AND d.error IS NULL
  AND d.sent_at >= now() - interval '7 days'
GROUP BY d.priority;
