from prometheus_client import Counter, Histogram

LLM_TOKEN_COUNT = Counter(
    "llm_token_count",
    "LLM token 计数",
    labelnames=["profile_name", "token_type", "provider", "model"],
)

LLM_DURATION = Histogram(
    "llm_duration_seconds",
    "LLM 接口调用耗时",
    labelnames=["profile_name", "provider", "model"],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
)

LLM_TOOL_USAGE_COUNT = Counter(
    "llm_tool_usage_count", "LLM 工具使用计数", labelnames=["tool_name", "provider", "model"]
)

LLM_SUCCESS_COUNT = Counter(
    "llm_success_count", "LLM 调用成功情况计数", labelnames=["type", "provider", "model"]
)

PLUGIN_CALL_COUNT = Counter("plugin_call_count", "插件调用次数", ["plugin"])

PLUGIN_DURATION = Histogram(
    "plugin_duration_seconds",
    "插件调用耗时",
    labelnames=["plugin"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
)
