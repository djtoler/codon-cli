# telemetry/mcp_trace_utils.py

import time
import inspect
from functools import wraps
from typing import Any, Dict, Optional
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode


def track_tools(tool_name: str, tool_type: str = "mcp"):
    """
    A decorator to create OpenTelemetry spans for MCP tool execution.
    Captures tool inputs, outputs, latency, and any errors.
    Now automatically handles LangChain's required 'config' parameter.
    """
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                tracer = trace.get_tracer(__name__)
                start_time = time.time()
                
                with tracer.start_as_current_span(f"tool.{tool_name}") as span:
                    # Set basic tool attributes
                    span.set_attribute("tool.name", tool_name)
                    span.set_attribute("tool.type", tool_type)
                    
                    # Capture input parameters (be careful not to log sensitive data)
                    # Filter out sensitive parameters for logging
                    safe_kwargs = {k: v for k, v in kwargs.items() if k not in ['config', 'run_manager']}
                    if safe_kwargs:
                        # Convert kwargs to string, truncate if too large
                        input_str = str(safe_kwargs)
                        if len(input_str) > 1000:
                            input_str = input_str[:1000] + "... [truncated]"
                        span.set_attribute("tool.input", input_str)
                    
                    # Log if we have a config parameter
                    if 'config' in kwargs:
                        span.set_attribute("tool.has_config", True)
                    
                    try:
                        # Smart parameter handling for LangChain compatibility
                        # Check if this is a LangChain _arun method that needs config
                        func_signature = inspect.signature(func)
                        if ('config' in func_signature.parameters and 
                            'config' not in kwargs and
                            func_signature.parameters['config'].default is inspect.Parameter.empty):
                            # This function requires 'config' but it's not provided, add it
                            kwargs['config'] = None
                        
                        result = await func(*args, **kwargs)
                        end_time = time.time()
                        
                        # Calculate and set latency
                        latency_ms = (end_time - start_time) * 1000
                        span.set_attribute("tool.latency_ms", latency_ms)
                        
                        # Capture output (truncated for large outputs)
                        if result is not None:
                            output_str = str(result)
                            if len(output_str) > 1000:
                                output_str = output_str[:1000] + "... [truncated]"
                            span.set_attribute("tool.output", output_str)
                            span.set_attribute("tool.output_length", len(str(result)))
                        
                        # Set success status
                        span.set_status(Status(StatusCode.OK))
                        
                        return result
                        
                    except Exception as e:
                        end_time = time.time()
                        latency_ms = (end_time - start_time) * 1000
                        span.set_attribute("tool.latency_ms", latency_ms)
                        
                        # Record the exception
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("tool.error", str(e))
                        span.set_attribute("tool.error_type", type(e).__name__)
                        
                        # Re-raise the exception
                        raise
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                tracer = trace.get_tracer(__name__)
                start_time = time.time()
                
                with tracer.start_as_current_span(f"tool.{tool_name}") as span:
                    # Set basic tool attributes
                    span.set_attribute("tool.name", tool_name)
                    span.set_attribute("tool.type", tool_type)
                    
                    # Capture input parameters (be careful not to log sensitive data)
                    # Filter out sensitive parameters for logging
                    safe_kwargs = {k: v for k, v in kwargs.items() if k not in ['config', 'run_manager']}
                    if safe_kwargs:
                        # Convert kwargs to string, truncate if too large
                        input_str = str(safe_kwargs)
                        if len(input_str) > 1000:
                            input_str = input_str[:1000] + "... [truncated]"
                        span.set_attribute("tool.input", input_str)
                    
                    # Log if we have a config parameter
                    if 'config' in kwargs:
                        span.set_attribute("tool.has_config", True)
                    
                    try:
                        # Smart parameter handling for LangChain compatibility
                        # Check if this function requires 'config' parameter
                        func_signature = inspect.signature(func)
                        if ('config' in func_signature.parameters and 
                            'config' not in kwargs and
                            func_signature.parameters['config'].default is inspect.Parameter.empty):
                            # This function requires 'config' but it's not provided, add it
                            kwargs['config'] = None
                        
                        result = func(*args, **kwargs)
                        end_time = time.time()
                        
                        # Calculate and set latency
                        latency_ms = (end_time - start_time) * 1000
                        span.set_attribute("tool.latency_ms", latency_ms)
                        
                        # Capture output (truncated for large outputs)
                        if result is not None:
                            output_str = str(result)
                            if len(output_str) > 1000:
                                output_str = output_str[:1000] + "... [truncated]"
                            span.set_attribute("tool.output", output_str)
                            span.set_attribute("tool.output_length", len(str(result)))
                        
                        # Set success status
                        span.set_status(Status(StatusCode.OK))
                        
                        return result
                        
                    except Exception as e:
                        end_time = time.time()
                        latency_ms = (end_time - start_time) * 1000
                        span.set_attribute("tool.latency_ms", latency_ms)
                        
                        # Record the exception
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("tool.error", str(e))
                        span.set_attribute("tool.error_type", type(e).__name__)
                        
                        # Re-raise the exception
                        raise
            
            return sync_wrapper
    
    return decorator


def track_langchain_tools(tool_name: str):
    """
    A specialized decorator for LangChain StructuredTool._arun methods that handles
    the required 'config' parameter correctly.
    """
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, config=None, **kwargs):
                tracer = trace.get_tracer(__name__)
                start_time = time.time()
                
                with tracer.start_as_current_span(f"langchain_tool.{tool_name}") as span:
                    # Set basic tool attributes
                    span.set_attribute("tool.name", tool_name)
                    span.set_attribute("tool.type", "langchain")
                    span.set_attribute("tool.has_config", config is not None)
                    
                    # Capture input parameters (excluding config for privacy)
                    if kwargs:
                        input_str = str(kwargs)
                        if len(input_str) > 1000:
                            input_str = input_str[:1000] + "... [truncated]"
                        span.set_attribute("tool.input", input_str)
                    
                    try:
                        # Pass config explicitly as required by LangChain
                        result = await func(*args, config=config, **kwargs)
                        end_time = time.time()
                        
                        # Calculate and set latency
                        latency_ms = (end_time - start_time) * 1000
                        span.set_attribute("tool.latency_ms", latency_ms)
                        
                        # Capture output (truncated for large outputs)
                        if result is not None:
                            output_str = str(result)
                            if len(output_str) > 1000:
                                output_str = output_str[:1000] + "... [truncated]"
                            span.set_attribute("tool.output", output_str)
                            span.set_attribute("tool.output_length", len(str(result)))
                        
                        # Set success status
                        span.set_status(Status(StatusCode.OK))
                        
                        return result
                        
                    except Exception as e:
                        end_time = time.time()
                        latency_ms = (end_time - start_time) * 1000
                        span.set_attribute("tool.latency_ms", latency_ms)
                        
                        # Record the exception
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("tool.error", str(e))
                        span.set_attribute("tool.error_type", type(e).__name__)
                        
                        # Re-raise the exception
                        raise
            
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, config=None, **kwargs):
                tracer = trace.get_tracer(__name__)
                start_time = time.time()
                
                with tracer.start_as_current_span(f"langchain_tool.{tool_name}") as span:
                    # Set basic tool attributes
                    span.set_attribute("tool.name", tool_name)
                    span.set_attribute("tool.type", "langchain")
                    span.set_attribute("tool.has_config", config is not None)
                    
                    # Capture input parameters (excluding config for privacy)
                    if kwargs:
                        input_str = str(kwargs)
                        if len(input_str) > 1000:
                            input_str = input_str[:1000] + "... [truncated]"
                        span.set_attribute("tool.input", input_str)
                    
                    try:
                        # Pass config explicitly as required by LangChain
                        result = func(*args, config=config, **kwargs)
                        end_time = time.time()
                        
                        # Calculate and set latency
                        latency_ms = (end_time - start_time) * 1000
                        span.set_attribute("tool.latency_ms", latency_ms)
                        
                        # Capture output (truncated for large outputs)
                        if result is not None:
                            output_str = str(result)
                            if len(output_str) > 1000:
                                output_str = output_str[:1000] + "... [truncated]"
                            span.set_attribute("tool.output", output_str)
                            span.set_attribute("tool.output_length", len(str(result)))
                        
                        # Set success status
                        span.set_status(Status(StatusCode.OK))
                        
                        return result
                        
                    except Exception as e:
                        end_time = time.time()
                        latency_ms = (end_time - start_time) * 1000
                        span.set_attribute("tool.latency_ms", latency_ms)
                        
                        # Record the exception
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        span.set_attribute("tool.error", str(e))
                        span.set_attribute("tool.error_type", type(e).__name__)
                        
                        # Re-raise the exception
                        raise
            
            return sync_wrapper
    
    return decorator


def extract_tool_metadata(tool_result: Any) -> Dict[str, Any]:
    """
    Extract metadata from tool execution results.
    This can be extended based on the specific structure of your MCP tool responses.
    """
    metadata = {}
    
    if isinstance(tool_result, dict):
        # Look for common metadata fields
        if 'execution_time' in tool_result:
            metadata['execution_time'] = tool_result['execution_time']
        if 'status' in tool_result:
            metadata['status'] = tool_result['status']
        if 'error' in tool_result:
            metadata['error'] = tool_result['error']
        # Add more fields as needed based on your MCP tool response structure
    
    return metadata


def enrich_tool_span_with_metadata(span: trace.Span, tool_result: Any, tool_name: str):
    """
    Enrich the tool span with additional metadata extracted from the tool result.
    """
    metadata = extract_tool_metadata(tool_result)
    
    for key, value in metadata.items():
        span.set_attribute(f"tool.{key}", value)
    
    # Add tool-specific enrichment logic here
    # For example, if certain tools return specific data structures
    if tool_name.startswith("github_"):
        # Add GitHub-specific metadata
        if isinstance(tool_result, dict) and 'repository' in tool_result:
            span.set_attribute("tool.github.repository", tool_result['repository'])
    elif tool_name.startswith("file_"):
        # Add file operation metadata
        if isinstance(tool_result, dict) and 'file_path' in tool_result:
            span.set_attribute("tool.file.path", tool_result['file_path'])