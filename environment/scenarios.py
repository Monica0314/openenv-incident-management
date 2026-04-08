import random
from typing import Dict, List

INCIDENT_SCENARIOS = {
    "easy": [
        {
            "service_name": "payment-service",
            "error_type": "connection_refused",
            "severity_signals": ["error_rate_100pct", "revenue_impact", "customer_facing"],
            "affected_services": ["checkout", "order-service"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: Connection refused at payment-service:8080 — socket timeout after 30s, 100% requests failing",
            "metrics": {"error_rate": 1.0, "p99_latency_ms": 9999.0, "requests_per_sec": 0.0},
            "ground_truth": {"severity": "P1", "team": "backend", "strategy": "hotfix"}
        },
        {
            "service_name": "auth-service",
            "error_type": "timeout",
            "severity_signals": ["latency_spike", "error_rate_high", "customer_facing"],
            "affected_services": ["user-portal", "mobile-app"],
            "recent_deployments": ["auth-service-v2.1.3"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: Auth token validation timeout after 5000ms at auth-service — JWT decode failure rate 94%",
            "metrics": {"error_rate": 0.94, "p99_latency_ms": 5200.0, "requests_per_sec": 120.0},
            "ground_truth": {"severity": "P1", "team": "backend", "strategy": "rollback"}
        },
        {
            "service_name": "recommendation-engine",
            "error_type": "high_latency",
            "severity_signals": ["latency_spike", "degraded_performance"],
            "affected_services": ["homepage"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "WARN: Recommendation engine p99 latency at 3200ms, above 2000ms threshold — non-critical feature degraded",
            "metrics": {"error_rate": 0.12, "p99_latency_ms": 3200.0, "requests_per_sec": 450.0},
            "ground_truth": {"severity": "P2", "team": "backend", "strategy": "monitor"}
        },
        {
            "service_name": "email-notification-service",
            "error_type": "queue_backlog",
            "severity_signals": ["queue_growing", "minor_delay"],
            "affected_services": [],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "INFO: Email queue backlog at 1200 messages, normal drain rate 200/min — estimated 6min delay",
            "metrics": {"error_rate": 0.02, "p99_latency_ms": 800.0, "requests_per_sec": 200.0},
            "ground_truth": {"severity": "P3", "team": "backend", "strategy": "monitor"}
        },
        {
            "service_name": "database-primary",
            "error_type": "replication_lag",
            "severity_signals": ["replication_lag_high", "read_degraded"],
            "affected_services": ["reporting-service", "analytics"],
            "recent_deployments": ["db-config-v1.0.2"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: Replication lag at 45s on db-replica-2, primary at db-primary:5432 — read queries failing on replica",
            "metrics": {"error_rate": 0.45, "p99_latency_ms": 4100.0, "requests_per_sec": 80.0},
            "ground_truth": {"severity": "P1", "team": "database", "strategy": "hotfix"}
        },
        {
            "service_name": "cdn-edge",
            "error_type": "ssl_certificate_expired",
            "severity_signals": ["ssl_error", "customer_facing", "security_alert"],
            "affected_services": ["web-frontend", "mobile-api"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: SSL certificate expired for cdn-edge.company.com — browsers rejecting connection, ERR_CERT_DATE_INVALID",
            "metrics": {"error_rate": 1.0, "p99_latency_ms": 0.0, "requests_per_sec": 0.0},
            "ground_truth": {"severity": "P1", "team": "security", "strategy": "hotfix"}
        },
        {
            "service_name": "search-service",
            "error_type": "OOM",
            "severity_signals": ["memory_exhausted", "service_restarting"],
            "affected_services": ["product-catalog"],
            "recent_deployments": ["search-service-v3.0.0"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "FATAL: Out of memory — search-service killed by OOM killer, RSS 8192MB exceeded limit, pod restarting",
            "metrics": {"error_rate": 0.88, "p99_latency_ms": 7800.0, "requests_per_sec": 30.0},
            "ground_truth": {"severity": "P1", "team": "devops", "strategy": "rollback"}
        },
        {
            "service_name": "reporting-dashboard",
            "error_type": "slow_query",
            "severity_signals": ["query_timeout", "internal_only"],
            "affected_services": [],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "WARN: Dashboard query timeout after 30s — analytics DB query missing index on created_at column",
            "metrics": {"error_rate": 0.30, "p99_latency_ms": 30000.0, "requests_per_sec": 5.0},
            "ground_truth": {"severity": "P2", "team": "database", "strategy": "hotfix"}
        },
        {
            "service_name": "api-gateway",
            "error_type": "rate_limit_misconfiguration",
            "severity_signals": ["legitimate_users_blocked", "error_rate_high"],
            "affected_services": ["all-downstream"],
            "recent_deployments": ["api-gateway-v4.2.1"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: API gateway rate limiter returning 429 to 78% of requests — config push set limit to 10 req/min instead of 10000",
            "metrics": {"error_rate": 0.78, "p99_latency_ms": 200.0, "requests_per_sec": 2000.0},
            "ground_truth": {"severity": "P1", "team": "devops", "strategy": "rollback"}
        },
        {
            "service_name": "logging-service",
            "error_type": "disk_full",
            "severity_signals": ["disk_usage_critical", "logs_dropping"],
            "affected_services": ["monitoring"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "WARN: Log aggregator disk at 98% — older logs being dropped, monitoring visibility degraded but services healthy",
            "metrics": {"error_rate": 0.0, "p99_latency_ms": 100.0, "requests_per_sec": 1000.0},
            "ground_truth": {"severity": "P3", "team": "devops", "strategy": "hotfix"}
        },
        {
            "service_name": "checkout-service",
            "error_type": "connection_pool_exhausted",
            "severity_signals": ["db_connections_maxed", "revenue_impact", "error_rate_high"],
            "affected_services": ["payment-service", "inventory"],
            "recent_deployments": ["checkout-v2.3.1"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: Connection pool exhausted at checkout-service — max 100 DB connections reached, new requests queuing, 67% timeout",
            "metrics": {"error_rate": 0.67, "p99_latency_ms": 8400.0, "requests_per_sec": 340.0},
            "ground_truth": {"severity": "P1", "team": "database", "strategy": "hotfix"}
        },
        {
            "service_name": "user-service",
            "error_type": "unusual_login_pattern",
            "severity_signals": ["auth_anomaly", "brute_force_detected"],
            "affected_services": [],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "SECURITY: 50,000 failed login attempts in 2min from 192.168.0.0/16 — credential stuffing attack detected on user-service",
            "metrics": {"error_rate": 0.05, "p99_latency_ms": 300.0, "requests_per_sec": 25000.0},
            "ground_truth": {"severity": "P1", "team": "security", "strategy": "escalate"}
        },
        {
            "service_name": "inventory-service",
            "error_type": "cache_miss_storm",
            "severity_signals": ["cache_miss_rate_high", "db_load_spike"],
            "affected_services": ["product-catalog", "checkout-service"],
            "recent_deployments": ["cache-config-v1.1"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "WARN: Redis cache miss rate at 95% after config change — all requests falling through to DB, causing 5x load spike",
            "metrics": {"error_rate": 0.22, "p99_latency_ms": 2800.0, "requests_per_sec": 600.0},
            "ground_truth": {"severity": "P2", "team": "backend", "strategy": "rollback"}
        },
        {
            "service_name": "kubernetes-node",
            "error_type": "node_not_ready",
            "severity_signals": ["node_failure", "pod_eviction"],
            "affected_services": ["multiple-services"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: k8s node worker-03 NotReady — kubelet stopped reporting, 12 pods evicted and rescheduling to other nodes",
            "metrics": {"error_rate": 0.35, "p99_latency_ms": 1200.0, "requests_per_sec": 800.0},
            "ground_truth": {"severity": "P2", "team": "devops", "strategy": "hotfix"}
        },
        {
            "service_name": "data-pipeline",
            "error_type": "schema_mismatch",
            "severity_signals": ["pipeline_failing", "data_loss_risk"],
            "affected_services": ["analytics", "ml-training"],
            "recent_deployments": ["pipeline-v2.0.0"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: Schema validation failed in data-pipeline — new field 'user_segment' missing in downstream consumer, records dropping",
            "metrics": {"error_rate": 1.0, "p99_latency_ms": 500.0, "requests_per_sec": 0.0},
            "ground_truth": {"severity": "P1", "team": "backend", "strategy": "rollback"}
        },
    ],
    "medium": [
        {
            "service_name": "payment-service",
            "error_type": "connection_refused",
            "severity_signals": ["error_rate_100pct", "revenue_impact"],
            "affected_services": ["checkout"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: payment-service refusing connections — port 8080 closed",
            "metrics": {"error_rate": 1.0, "p99_latency_ms": 9999.0, "requests_per_sec": 0.0},
            "ground_truth": {"severity": "P1", "team": "backend", "strategy": "hotfix"}
        },
        {
            "service_name": "database-primary",
            "error_type": "connection_pool_exhausted",
            "severity_signals": ["db_connections_maxed", "query_timeout"],
            "affected_services": ["checkout-service", "user-service"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: DB connection pool at max 200 — new connections refused, query queue depth 1500",
            "metrics": {"error_rate": 0.72, "p99_latency_ms": 6000.0, "requests_per_sec": 150.0},
            "ground_truth": {"severity": "P1", "team": "database", "strategy": "hotfix"}
        },
        {
            "service_name": "api-gateway",
            "error_type": "config_error",
            "severity_signals": ["all_routes_affected", "deployment_related"],
            "affected_services": ["all-services"],
            "recent_deployments": ["api-gateway-v5.0.0"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: Nginx config syntax error after deploy — upstream block missing, 502 Bad Gateway on all routes",
            "metrics": {"error_rate": 1.0, "p99_latency_ms": 0.0, "requests_per_sec": 0.0},
            "ground_truth": {"severity": "P1", "team": "devops", "strategy": "rollback"}
        },
        {
            "service_name": "auth-service",
            "error_type": "certificate_expired",
            "severity_signals": ["ssl_error", "auth_failing", "security_alert"],
            "affected_services": ["all-services"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: mTLS certificate expired for auth-service — all service-to-service auth failing",
            "metrics": {"error_rate": 0.95, "p99_latency_ms": 100.0, "requests_per_sec": 50.0},
            "ground_truth": {"severity": "P1", "team": "security", "strategy": "hotfix"}
        },
        {
            "service_name": "search-service",
            "error_type": "high_latency",
            "severity_signals": ["latency_spike", "partial_degradation"],
            "affected_services": ["product-catalog"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "WARN: Search p99 at 4500ms — Elasticsearch shard rebalancing causing temporary slowdown",
            "metrics": {"error_rate": 0.15, "p99_latency_ms": 4500.0, "requests_per_sec": 300.0},
            "ground_truth": {"severity": "P2", "team": "backend", "strategy": "monitor"}
        },
        {
            "service_name": "kubernetes-cluster",
            "error_type": "node_failure",
            "severity_signals": ["node_not_ready", "pod_eviction"],
            "affected_services": ["multiple"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: 3 k8s nodes NotReady — cluster autoscaler triggered, new nodes provisioning",
            "metrics": {"error_rate": 0.40, "p99_latency_ms": 2000.0, "requests_per_sec": 500.0},
            "ground_truth": {"severity": "P1", "team": "devops", "strategy": "escalate"}
        },
        {
            "service_name": "notification-service",
            "error_type": "queue_backlog",
            "severity_signals": ["queue_growing", "delayed_delivery"],
            "affected_services": [],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "WARN: SQS queue depth at 50k messages — consumer lag growing, notifications delayed by 15min",
            "metrics": {"error_rate": 0.05, "p99_latency_ms": 900000.0, "requests_per_sec": 100.0},
            "ground_truth": {"severity": "P2", "team": "backend", "strategy": "hotfix"}
        },
        {
            "service_name": "data-warehouse",
            "error_type": "replication_lag",
            "severity_signals": ["replication_lag_high", "stale_data"],
            "affected_services": ["reporting", "analytics"],
            "recent_deployments": ["dw-pipeline-v1.3"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: DW replication lag 2 hours behind — reports showing stale data from 2hrs ago",
            "metrics": {"error_rate": 0.0, "p99_latency_ms": 200.0, "requests_per_sec": 20.0},
            "ground_truth": {"severity": "P2", "team": "database", "strategy": "rollback"}
        },
        {
            "service_name": "user-service",
            "error_type": "brute_force_attack",
            "severity_signals": ["auth_anomaly", "rate_spike", "security_alert"],
            "affected_services": [],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "SECURITY: 100k login attempts/min detected from rotating IPs — account lockout triggered for 500 users",
            "metrics": {"error_rate": 0.10, "p99_latency_ms": 400.0, "requests_per_sec": 100000.0},
            "ground_truth": {"severity": "P1", "team": "security", "strategy": "escalate"}
        },
        {
            "service_name": "cdn",
            "error_type": "origin_timeout",
            "severity_signals": ["cache_miss_high", "origin_overloaded"],
            "affected_services": ["web-frontend"],
            "recent_deployments": ["cdn-config-v2.1"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "ERROR: CDN cache-control headers set to no-cache after config push — all requests hitting origin, origin overloaded",
            "metrics": {"error_rate": 0.55, "p99_latency_ms": 5000.0, "requests_per_sec": 3000.0},
            "ground_truth": {"severity": "P1", "team": "devops", "strategy": "rollback"}
        },
    ],
    "hard": [
        {
            "service_name": "order-service",
            "error_type": "cascade_failure",
            "severity_signals": ["multiple_services_down", "revenue_impact", "error_rate_high"],
            "affected_services": ["payment-service", "inventory-service", "notification-service", "analytics-service"],
            "recent_deployments": ["order-service-v3.1.0"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: order-service v3.1.0 deploy introduced memory leak — heap growing 50MB/min, causing downstream timeout cascade across 4 services",
            "metrics": {"error_rate": 0.89, "p99_latency_ms": 12000.0, "requests_per_sec": 45.0},
            "ground_truth": {
                "severity": "P1",
                "team": "backend",
                "strategy": "rollback",
                "root_cause_service": "order-service",
                "misdirection": False,
                "cascade_chain": ["order-service", "payment-service", "inventory-service", "notification-service", "analytics-service"]
            }
        },
        {
            "service_name": "database-primary",
            "error_type": "cascade_failure",
            "severity_signals": ["db_overloaded", "all_services_slow", "connection_refused"],
            "affected_services": ["user-service", "checkout-service", "reporting-service", "search-service"],
            "recent_deployments": [],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: DB primary CPU at 100% — slow query from reporting-service caused lock contention, cascading to all DB-dependent services",
            "metrics": {"error_rate": 0.76, "p99_latency_ms": 15000.0, "requests_per_sec": 20.0},
            "ground_truth": {
                "severity": "P1",
                "team": "database",
                "strategy": "hotfix",
                "root_cause_service": "database-primary",
                "misdirection": False,
                "cascade_chain": ["database-primary", "user-service", "checkout-service", "reporting-service", "search-service"]
            }
        },
        {
            "service_name": "api-gateway",
            "error_type": "cascade_failure",
            "severity_signals": ["gateway_misconfigured", "all_routes_affected", "recent_deploy"],
            "affected_services": ["auth-service", "payment-service", "user-service", "order-service"],
            "recent_deployments": ["api-gateway-v6.0.0", "auth-service-v2.2.0"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: api-gateway routing table corrupted after v6.0.0 deploy — auth-service appears healthy but is unreachable, causing auth failures cascading downstream. NOTE: auth-service logs show errors but root cause is gateway config.",
            "metrics": {"error_rate": 0.92, "p99_latency_ms": 8000.0, "requests_per_sec": 10.0},
            "ground_truth": {
                "severity": "P1",
                "team": "devops",
                "strategy": "rollback",
                "root_cause_service": "api-gateway",
                "misdirection": True,
                "misdirection_service": "auth-service",
                "cascade_chain": ["api-gateway", "auth-service", "payment-service", "user-service", "order-service"]
            }
        },
        {
            "service_name": "message-broker",
            "error_type": "cascade_failure",
            "severity_signals": ["broker_overloaded", "consumers_lagging", "producer_blocking"],
            "affected_services": ["order-service", "notification-service", "analytics-service", "inventory-service"],
            "recent_deployments": ["message-broker-v2.0.0"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: Kafka broker disk 100% — new v2.0.0 log retention config set to never-delete, broker refusing new messages, all producers blocking",
            "metrics": {"error_rate": 0.85, "p99_latency_ms": 20000.0, "requests_per_sec": 5.0},
            "ground_truth": {
                "severity": "P1",
                "team": "devops",
                "strategy": "rollback",
                "root_cause_service": "message-broker",
                "misdirection": False,
                "cascade_chain": ["message-broker", "order-service", "notification-service", "analytics-service", "inventory-service"]
            }
        },
        {
            "service_name": "load-balancer",
            "error_type": "cascade_failure",
            "severity_signals": ["health_checks_failing", "traffic_misrouted", "recent_deploy"],
            "affected_services": ["payment-service", "user-service", "order-service", "search-service"],
            "recent_deployments": ["load-balancer-v3.0.0", "payment-service-v1.9.0"],
            "active_teams": {"backend": 3, "database": 2, "devops": 4, "security": 1},
            "raw_log": "CRITICAL: LB health checks passing but traffic routing to wrong backend pool after v3.0.0 deploy — payment-service errors look like payment bugs but root cause is load balancer misconfiguration",
            "metrics": {"error_rate": 0.78, "p99_latency_ms": 9500.0, "requests_per_sec": 25.0},
            "ground_truth": {
                "severity": "P1",
                "team": "devops",
                "strategy": "rollback",
                "root_cause_service": "load-balancer",
                "misdirection": True,
                "misdirection_service": "payment-service",
                "cascade_chain": ["load-balancer", "payment-service", "user-service", "order-service", "search-service"]
            }
        },
    ]
}

TEAM_CAPACITY = {
    "backend": 3,
    "database": 2,
    "devops": 4,
    "security": 1
}


def get_scenario(task_difficulty: str, seed: int) -> dict:
    random.seed(seed)
    scenarios = INCIDENT_SCENARIOS[task_difficulty]
    idx = seed % len(scenarios)
    return scenarios[idx]


def get_all_scenarios(task_difficulty: str) -> List[dict]:
    return INCIDENT_SCENARIOS[task_difficulty]


def get_team_capacity() -> Dict[str, int]:
    return TEAM_CAPACITY.copy()