# _mcp/tools.py
"""
Centralized tool registry with LangChain wrappers, telemetry, and MCP registration.
"""
from __future__ import annotations
import asyncio
from typing import Dict, List, Callable, Any, Optional
from functools import wraps
import time
from langchain_core.tools import tool, BaseTool

from telemetry.mcp_trace_utils import track_tools


# ---------- Resiliency decorator ----------
def resilient(retries: int = 1, timeout_sec: Optional[float] = None):
    """Retry a tool and enforce a soft timeout."""
    def deco(fn: Callable[..., Any]):
        @wraps(fn)
        def inner(*args, **kwargs):
            last_err = None
            for attempt in range(retries + 1):
                start = time.perf_counter()
                try:
                    result = fn(*args, **kwargs)
                    if timeout_sec is not None and (time.perf_counter() - start) > timeout_sec:
                        raise TimeoutError(f"Tool '{fn.__name__}' exceeded {timeout_sec}s")
                    return result
                except Exception as e:
                    last_err = e
                    if attempt >= retries:
                        raise
            raise last_err
        return inner
    return deco


# ---------- Core tool implementations ----------
def get_weather_impl(city: str) -> str:
    """Return a short, friendly weather snippet for the given city."""
    return f"It's always sunny in {city}."

def add_impl(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return a + b

def healthcheck_impl() -> str:
    """Return 'OK' to verify that the tool runner is healthy."""
    return "OK"


# ---------- LangChain tools with telemetry ----------
@tool
@resilient(retries=1, timeout_sec=3.0)
def get_weather(city: str) -> str:
    """Return a short, friendly weather snippet for the given city."""
    return get_weather_impl(city)

@tool
def add(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    return add_impl(a, b)

@tool
def healthcheck() -> str:
    """Return 'OK' to verify that the tool runner is healthy."""
    return healthcheck_impl()


# ---------- Tool registry ----------
TOOLS: Dict[str, Any] = {
    "get_weather": get_weather,
    "add": add,
    "healthcheck": healthcheck,
}

BUNDLES: Dict[str, List[str]] = {
    "math": ["add"],
    "utilities": ["get_weather", "healthcheck"],
    "ops": ["healthcheck"],
}


# ---------- MCP registration ----------
def register_mcp_tools(mcp):
    """Register tools with MCP server."""
    
    @mcp.tool(name="get_weather", title="Get Weather", description="Get weather for a city.")
    def mcp_get_weather(city: str) -> str:
        return get_weather_impl(city)

    @mcp.tool(name="add", title="Add Numbers", description="Add two integers.")
    def mcp_add(a: int, b: int) -> int:
        return add_impl(a, b)

    @mcp.tool(name="healthcheck", title="Health Check", description="Check system health.")
    def mcp_healthcheck() -> str:
        return healthcheck_impl()


# ---------- Telemetry wrapping for MCP-sourced tools ----------
def wrap_tools_with_telemetry(tools: List[BaseTool]) -> List[BaseTool]:
    """Apply telemetry wrapping to tools from MCP."""
    wrapped = []
    for t in tools:
        if asyncio.iscoroutinefunction(getattr(t, "_run", None)):
            print(f"Wrapping tool._run: {t.name}")
            t._run = track_tools(tool_name=t.name)(t._run)
        elif asyncio.iscoroutinefunction(getattr(t, "_arun", None)):
            print(f"Wrapping tool._arun: {t.name}")
            t._arun = track_tools(tool_name=t.name)(t._arun)
        elif callable(getattr(t, "_run", None)):
            print(f"Wrapping sync tool._run: {t.name}")
            t._run = track_tools(tool_name=t.name)(t._run)
        else:
            print(f"NOT wrapping tool: {t.name} - no suitable method found")
        wrapped.append(t)
    return wrapped


def validate_bundle_names() -> bool:
    """Ensure all bundle references point to actual tool names."""
    unknown = [(b, n) for b, names in BUNDLES.items() for n in names if n not in TOOLS]
    if unknown:
        pairs = ", ".join(f"{b}:{n}" for b, n in unknown)
        raise ValueError(f"BUNDLES reference unknown tools: {pairs}")
    return True

validate_bundle_names()