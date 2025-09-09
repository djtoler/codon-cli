

import os
import hashlib
import inspect
import time
from functools import wraps
from typing import Optional, Any, Dict
from opentelemetry import trace
# from opentelemetry.trace import Span
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import BatchSpanProcessor
# from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
# from opentelemetry.sdk.resources import Resource
from langchain_core.messages import AIMessage


def create_agent_id(name: str, role: Optional[str] = None) -> str:
    """Create a unique agent ID based on name and role."""
    import hashlib
    agent_str = f"{name}:{role}" if role else name
    return hashlib.sha256(agent_str.encode()).hexdigest()


def extract_llm_metadata(result: Any) -> Dict[str, Any]:
    """
    Extract LLM metadata from the result, including model info, tokens, and other metrics.
    """
    metadata = {}
    
    # Handle dictionary results with 'messages' key
    if isinstance(result, dict) and 'messages' in result:
        messages = result['messages']
        if isinstance(messages, list):
            for msg in messages:
                if isinstance(msg, AIMessage):
                    # Extract model information
                    if hasattr(msg, 'response_metadata'):
                        resp_meta = msg.response_metadata
                        
                        # Model information
                        if 'model_name' in resp_meta:
                            metadata['model_name'] = resp_meta['model_name']
                        
                        # Token usage information
                        if 'token_usage' in resp_meta:
                            token_usage = resp_meta['token_usage']
                            metadata['input_tokens'] = token_usage.get('prompt_tokens', 0)
                            metadata['output_tokens'] = token_usage.get('completion_tokens', 0)
                            metadata['total_tokens'] = token_usage.get('total_tokens', 0)
                            
                            # Detailed token information if available
                            if 'completion_tokens_details' in token_usage:
                                details = token_usage['completion_tokens_details']
                                metadata['reasoning_tokens'] = details.get('reasoning_tokens', 0)
                                metadata['audio_tokens'] = details.get('audio_tokens', 0)
                            
                            if 'prompt_tokens_details' in token_usage:
                                details = token_usage['prompt_tokens_details']
                                metadata['cached_tokens'] = details.get('cached_tokens', 0)
                        
                        # System information
                        if 'system_fingerprint' in resp_meta:
                            metadata['system_fingerprint'] = resp_meta['system_fingerprint']
                        
                        if 'service_tier' in resp_meta:
                            metadata['service_tier'] = resp_meta['service_tier']
                        
                        if 'finish_reason' in resp_meta:
                            metadata['finish_reason'] = resp_meta['finish_reason']
                    
                    # Also check usage_metadata if available
                    if hasattr(msg, 'usage_metadata'):
                        usage_meta = msg.usage_metadata
                        if usage_meta:
                            # Update token counts if not already set
                            if 'input_tokens' not in metadata and hasattr(usage_meta, 'input_tokens'):
                                metadata['input_tokens'] = usage_meta.input_tokens
                            if 'output_tokens' not in metadata and hasattr(usage_meta, 'output_tokens'):
                                metadata['output_tokens'] = usage_meta.output_tokens
                            if 'total_tokens' not in metadata and hasattr(usage_meta, 'total_tokens'):
                                metadata['total_tokens'] = usage_meta.total_tokens
                    
                    # Extract content length as a fallback metric
                    if hasattr(msg, 'content') and msg.content:
                        metadata['response_length'] = len(str(msg.content))
                    
                    break  # Process only the first AIMessage
    
    return metadata


def enrich_span_with_llm_metadata(
    span: trace.Span,
    result: Any,
    start_time: float,
    end_time: float
):
    """
    Enrich the span with LLM-specific metadata including model, tokens, and latency.
    """
    # Calculate latency
    latency_ms = (end_time - start_time) * 1000
    span.set_attribute("llm.latency_ms", latency_ms)
    
    # Extract and set LLM metadata
    metadata = extract_llm_metadata(result)
    
    # Set model attributes
    if 'model_name' in metadata:
        span.set_attribute("llm.model", metadata['model_name'])
    
    # Set token usage attributes
    if 'input_tokens' in metadata:
        span.set_attribute("llm.usage.input_tokens", metadata['input_tokens'])
    if 'output_tokens' in metadata:
        span.set_attribute("llm.usage.output_tokens", metadata['output_tokens'])
    if 'total_tokens' in metadata:
        span.set_attribute("llm.usage.total_tokens", metadata['total_tokens'])
    
    # Set detailed token attributes if available
    if 'reasoning_tokens' in metadata:
        span.set_attribute("llm.usage.reasoning_tokens", metadata['reasoning_tokens'])
    if 'cached_tokens' in metadata:
        span.set_attribute("llm.usage.cached_tokens", metadata['cached_tokens'])
    if 'audio_tokens' in metadata:
        span.set_attribute("llm.usage.audio_tokens", metadata['audio_tokens'])
    
    # Set system attributes
    if 'system_fingerprint' in metadata:
        span.set_attribute("llm.system_fingerprint", metadata['system_fingerprint'])
    if 'service_tier' in metadata:
        span.set_attribute("llm.service_tier", metadata['service_tier'])
    if 'finish_reason' in metadata:
        span.set_attribute("llm.finish_reason", metadata['finish_reason'])
    
    # Set response size
    if 'response_length' in metadata:
        span.set_attribute("llm.response_length", metadata['response_length'])
    
    # Calculate tokens per second if we have the data
    if 'total_tokens' in metadata and latency_ms > 0:
        tokens_per_second = (metadata['total_tokens'] / latency_ms) * 1000
        span.set_attribute("llm.tokens_per_second", tokens_per_second)


def track_agent(
    node_name: str,
    is_agent: bool = False,
    agent_role: Optional[str] = None):

    """
    A decorator to create an OpenTelemetry span for a LangGraph node.
    Captures model information, token usage, and latency for LLM nodes.
    """
    agent_id = (
        None if not is_agent else create_agent_id(name=node_name, role=agent_role)
    )
    
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def awrapper(*args, **kwargs):
                tracer = trace.get_tracer(__name__)
                start_time = time.time()
                
                with tracer.start_as_current_span(node_name) as span:
                    span.set_attribute("langgraph.node.name", node_name)
                    
                    # Set agent attributes if applicable
                    if is_agent and agent_id:
                        span.set_attribute("codon.is_agent", is_agent)
                        span.set_attribute("codon.agent.id", agent_id)
                        if agent_role:
                            span.set_attribute("codon.agent.role", agent_role)
                    
                    try:
                        result = await func(*args, **kwargs)
                        end_time = time.time()
                        
                        # Set output (truncated for large outputs)
                        output_str = str(result)
                        if len(output_str) > 1000:
                            output_str = output_str[:1000] + "... [truncated]"
                        span.set_attribute("langgraph.node.outputs", output_str)
                        
                        # Enrich with LLM metadata if this is an agent node
                        if is_agent:
                            enrich_span_with_llm_metadata(span, result, start_time, end_time)
                        else:
                            # Still set latency for non-agent nodes
                            latency_ms = (end_time - start_time) * 1000
                            span.set_attribute("node.latency_ms", latency_ms)
                        
                        # Set status to OK
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        
                    except Exception as e:
                        # Record exception and set error status
                        span.record_exception(e)
                        span.set_status(
                            trace.Status(trace.StatusCode.ERROR, str(e))
                        )
                        raise
                    
                    return result
            
            return awrapper
        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                tracer = trace.get_tracer(__name__)
                start_time = time.time()
                
                with tracer.start_as_current_span(node_name) as span:
                    span.set_attribute("langgraph.node.name", node_name)
                    
                    # Set agent attributes if applicable
                    if is_agent and agent_id:
                        span.set_attribute("codon.is_agent", is_agent)
                        span.set_attribute("codon.agent.id", agent_id)
                        if agent_role:
                            span.set_attribute("codon.agent.role", agent_role)
                    
                    try:
                        result = func(*args, **kwargs)
                        end_time = time.time()
                        
                        # Set output (truncated for large outputs)
                        output_str = str(result)
                        if len(output_str) > 1000:
                            output_str = output_str[:1000] + "... [truncated]"
                        span.set_attribute("langgraph.node.outputs", output_str)
                        
                        # Enrich with LLM metadata if this is an agent node
                        if is_agent:
                            enrich_span_with_llm_metadata(span, result, start_time, end_time)
                        else:
                            # Still set latency for non-agent nodes
                            latency_ms = (end_time - start_time) * 1000
                            span.set_attribute("node.latency_ms", latency_ms)
                        
                        # Set status to OK
                        span.set_status(trace.Status(trace.StatusCode.OK))
                        
                    except Exception as e:
                        # Record exception and set error status
                        span.record_exception(e)
                        span.set_status(
                            trace.Status(trace.StatusCode.ERROR, str(e))
                        )
                        raise
                    
                    return result
            
            return wrapper
    
    return decorator