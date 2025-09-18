# config/llm.py
"""
Model classes for handling OpenRouter pricing data and model selection.
Clean, focused classes following the NodeInfo pattern.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum
import json
import uuid
import os
from pathlib import Path

# ---------- Enums ----------
class ModelProvider(Enum):
    # LangChain-supported providers (exact strings from init_chat_model)
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    AZURE_OPENAI = "azure_openai"
    AZURE_AI = "azure_ai"
    GOOGLE_VERTEXAI = "google_vertexai"
    GOOGLE_GENAI = "google_genai"
    GOOGLE_ANTHROPIC_VERTEX = "google_anthropic_vertex"
    BEDROCK = "bedrock"
    BEDROCK_CONVERSE = "bedrock_converse"
    COHERE = "cohere"
    FIREWORKS = "fireworks"
    TOGETHER = "together"
    MISTRALAI = "mistralai"
    HUGGINGFACE = "huggingface"
    GROQ = "groq"
    OLLAMA = "ollama"
    DEEPSEEK = "deepseek"
    IBM = "ibm"
    NVIDIA = "nvidia"
    XAI = "xai"
    PERPLEXITY = "perplexity"
    
    # Additional providers
    OPENROUTER = "openrouter"
    LOCAL = "local"
    UNKNOWN = "unknown"


class ModelTier(Enum):
    PREMIUM = "premium"      # Most expensive, highest quality
    BALANCED = "balanced"    # Good balance of cost/quality
    EFFICIENT = "efficient"  # Lower cost, decent quality
    BUDGET = "budget"        # Cheapest options


# Add this to your existing llms.py file

class ModelConfig(BaseModel):
    """Configuration for how a role should use a model"""
    model_config = ConfigDict(validate_assignment=True)
    
    model_id: Optional[str] = None
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None

# ---------- 1. Model Pricing ----------
class ModelPricing(BaseModel):
    """Handles pricing information for a model"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Pricing per 1K tokens (from OpenRouter)
    prompt_per_1k_tokens: float
    completion_per_1k_tokens: float
    
    # Pricing per 1M tokens (convenience)
    prompt_per_1m_tokens: float
    completion_per_1m_tokens: float
    
    @classmethod
    def from_openrouter_data(cls, pricing_data: Dict[str, float]) -> 'ModelPricing':
        """Create from OpenRouter JSON pricing data"""
        return cls(
            prompt_per_1k_tokens=pricing_data.get("prompt_per_1k_tokens", 0.0),
            completion_per_1k_tokens=pricing_data.get("completion_per_1k_tokens", 0.0),
            prompt_per_1m_tokens=pricing_data.get("prompt_per_1m_tokens", 0.0),
            completion_per_1m_tokens=pricing_data.get("completion_per_1m_tokens", 0.0)
        )
    
    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate total cost for given token counts"""
        prompt_cost = (prompt_tokens / 1000) * self.prompt_per_1k_tokens
        completion_cost = (completion_tokens / 1000) * self.completion_per_1k_tokens
        return prompt_cost + completion_cost
    
    def get_avg_cost_per_1k_tokens(self) -> float:
        """Get average cost per 1K tokens (useful for rough estimates)"""
        return (self.prompt_per_1k_tokens + self.completion_per_1k_tokens) / 2
    
    def is_free(self) -> bool:
        """Check if model is free to use"""
        return (self.prompt_per_1k_tokens == 0.0 and 
                self.completion_per_1k_tokens == 0.0)


# ---------- 2. Model Info ----------
class ModelInfo(BaseModel):
    """Core model information and capabilities"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Identity
    model_id: str  # e.g., "google/gemini-2.5-flash"
    name: str      # e.g., "Gemini 2.5 Flash"
    provider: ModelProvider
    
    # Capabilities
    context_length: int
    supports_tools: bool = True
    supports_vision: bool = False
    supports_code: bool = True
    
    # Performance estimates (can be updated from real usage)
    estimated_speed_tier: int = 3  # 1=fastest, 5=slowest
    estimated_quality_tier: int = 3  # 1=highest, 5=lowest
    
    @classmethod
    def from_model_id(cls, model_id: str, openrouter_data: Dict[str, Any]) -> 'ModelInfo':
        """Create ModelInfo from OpenRouter model ID and data"""
        # Extract provider from model_id using LangChain inference patterns
        provider = ModelProvider.UNKNOWN
        
        # First, try explicit provider from model_id format "provider/model"
        if '/' in model_id:
            provider_str = model_id.split('/')[0].lower()
            try:
                # Map common OpenRouter providers to LangChain providers
                provider_mapping = {
                    'openai': ModelProvider.OPENAI,
                    'anthropic': ModelProvider.ANTHROPIC,
                    'google': ModelProvider.GOOGLE_VERTEXAI,  # Default Google to VertexAI
                    'meta': ModelProvider.HUGGINGFACE,  # Meta models often via HuggingFace
                    'mistral': ModelProvider.MISTRALAI,
                    'cohere': ModelProvider.COHERE,
                    'amazon': ModelProvider.BEDROCK,
                    'deepseek': ModelProvider.DEEPSEEK,
                    'xai': ModelProvider.XAI,
                    'perplexity': ModelProvider.PERPLEXITY,
                }
                provider = provider_mapping.get(provider_str, ModelProvider.OPENROUTER)
            except ValueError:
                provider = ModelProvider.OPENROUTER
        else:
            # Use LangChain's model prefix inference patterns
            model_lower = model_id.lower()
            
            if any(model_lower.startswith(prefix) for prefix in ['gpt-3', 'gpt-4', 'o1', 'o3']):
                provider = ModelProvider.OPENAI
            elif model_lower.startswith('claude'):
                provider = ModelProvider.ANTHROPIC
            elif model_lower.startswith('amazon'):
                provider = ModelProvider.BEDROCK
            elif model_lower.startswith('gemini'):
                provider = ModelProvider.GOOGLE_VERTEXAI
            elif model_lower.startswith('command'):
                provider = ModelProvider.COHERE
            elif model_lower.startswith('accounts/fireworks'):
                provider = ModelProvider.FIREWORKS
            elif model_lower.startswith('mistral'):
                provider = ModelProvider.MISTRALAI
            elif model_lower.startswith('deepseek'):
                provider = ModelProvider.DEEPSEEK
            elif model_lower.startswith('grok'):
                provider = ModelProvider.XAI
            elif model_lower.startswith('sonar'):
                provider = ModelProvider.PERPLEXITY
        
        # Create friendly name from ID
        name = model_id.split('/')[-1].replace('-', ' ').title()
        
        # Determine capabilities based on model name patterns
        supports_vision = any(keyword in model_id.lower() for keyword in [
            'vision', 'gpt-4', 'claude-3', 'gemini', 'gpt-4o'
        ])
        
        supports_tools = True  # Most modern models support tools
        
        return cls(
            model_id=model_id,
            name=name,
            provider=provider,
            context_length=openrouter_data.get("context_length", 8192),
            supports_tools=supports_tools,
            supports_vision=supports_vision,
            supports_code=True
        )


# ---------- 3. Model Performance Tracker ----------
class ModelPerformanceTracker(BaseModel):
    """Tracks actual performance metrics for a model"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Usage statistics
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cost_usd: float = 0.0
    
    # Performance metrics
    avg_latency_ms: float = 0.0
    avg_tokens_per_second: float = 0.0
    success_rate: float = 1.0
    
    # Recent usage (for moving averages)
    recent_latencies: List[float] = Field(default_factory=list, exclude=True)
    
    def log_request(self, prompt_tokens: int, completion_tokens: int, 
                   latency_ms: float, cost_usd: float, success: bool = True):
        """Log a request for performance tracking"""
        self.total_requests += 1
        self.total_prompt_tokens += prompt_tokens
        self.total_completion_tokens += completion_tokens
        self.total_cost_usd += cost_usd
        
        # Update latency (moving average)
        if len(self.recent_latencies) >= 100:
            self.recent_latencies.pop(0)
        self.recent_latencies.append(latency_ms)
        
        if self.total_requests == 1:
            self.avg_latency_ms = latency_ms
        else:
            alpha = 0.1
            self.avg_latency_ms = alpha * latency_ms + (1 - alpha) * self.avg_latency_ms
        
        # Update tokens per second
        if latency_ms > 0:
            tokens_per_second = (completion_tokens * 1000) / latency_ms
            if self.total_requests == 1:
                self.avg_tokens_per_second = tokens_per_second
            else:
                self.avg_tokens_per_second = (
                    alpha * tokens_per_second + (1 - alpha) * self.avg_tokens_per_second
                )
        
        # Update success rate
        if self.total_requests == 1:
            self.success_rate = 1.0 if success else 0.0
        else:
            alpha = 0.1
            current_success = 1.0 if success else 0.0
            self.success_rate = alpha * current_success + (1 - alpha) * self.success_rate
    
    def get_avg_cost_per_request(self) -> float:
        """Get average cost per request"""
        if self.total_requests == 0:
            return 0.0
        return self.total_cost_usd / self.total_requests


# ---------- 4. Main Model Class ----------
class Model(BaseModel):
    """Complete model with info, pricing, and performance tracking"""
    model_config = ConfigDict(validate_assignment=True)
    
    # Core components
    info: ModelInfo
    pricing: ModelPricing
    performance: ModelPerformanceTracker = Field(default_factory=ModelPerformanceTracker)
    
    # Model state
    is_enabled: bool = True
    is_deprecated: bool = False
    
    @classmethod
    def from_openrouter_data(cls, model_id: str, data: Dict[str, Any]) -> 'Model':
        """Create Model from OpenRouter JSON data"""
        info = ModelInfo.from_model_id(model_id, data)
        pricing = ModelPricing.from_openrouter_data(data.get("pricing", {}))
        
        return cls(info=info, pricing=pricing)
    
    def calculate_request_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate cost for a request"""
        return self.pricing.calculate_cost(prompt_tokens, completion_tokens)
    
    def log_usage(self, prompt_tokens: int, completion_tokens: int, 
                  latency_ms: float, success: bool = True):
        """Log usage and update performance metrics"""
        cost = self.calculate_request_cost(prompt_tokens, completion_tokens)
        self.performance.log_request(
            prompt_tokens, completion_tokens, latency_ms, cost, success
        )
    
    def get_tier(self) -> ModelTier:
        """Determine model tier based on pricing"""
        avg_cost = self.pricing.get_avg_cost_per_1k_tokens()
        
        if avg_cost >= 0.020:  # $20+ per 1M tokens
            return ModelTier.PREMIUM
        elif avg_cost >= 0.005:  # $5+ per 1M tokens
            return ModelTier.BALANCED
        elif avg_cost >= 0.001:  # $1+ per 1M tokens
            return ModelTier.EFFICIENT
        else:  # < $1 per 1M tokens
            return ModelTier.BUDGET
    
    def is_cheaper_than(self, other_model: 'Model') -> bool:
        """Check if this model is cheaper than another"""
        return (self.pricing.get_avg_cost_per_1k_tokens() < 
                other_model.pricing.get_avg_cost_per_1k_tokens())


# ---------- 5. Model Registry ----------
class ModelRegistry(BaseModel):
    """Registry of all available models with management capabilities"""
    model_config = ConfigDict(validate_assignment=True)
    
    models: Dict[str, Model] = Field(default_factory=dict)
    
    # At the top of your ModelRegistry class, update the load method:
    @classmethod
    def load_from_openrouter_json(cls, json_path: str) -> 'ModelRegistry':
        """Load models from OpenRouter pricing JSON file"""
        registry = cls()
        
        # Get the directory where this script is located
        script_dir = Path(__file__).parent
        full_path = script_dir / json_path
        
        try:
            with open(full_path, 'r') as f:
                data = json.load(f)
            
            for model_id, model_data in data.items():
                try:
                    model = Model.from_openrouter_data(model_id, model_data)
                    registry.models[model_id] = model
                except Exception as e:
                    print(f"Warning: Could not load model {model_id}: {e}")
            
            return registry
            
        except FileNotFoundError:
            print(f"File not found: {full_path}")
            print(f"Current working directory: {os.getcwd()}")
            print(f"Script directory: {script_dir}")
            raise
    
    def get_model(self, model_id: str) -> Optional[Model]:
        """Get a model by ID"""
        return self.models.get(model_id)
    
    def get_models_by_provider(self, provider: ModelProvider) -> List[Model]:
        """Get all models from a specific provider"""
        return [m for m in self.models.values() if m.info.provider == provider]
    
    def get_models_by_tier(self, tier: ModelTier) -> List[Model]:
        """Get all models in a specific tier"""
        return [m for m in self.models.values() if m.get_tier() == tier]
    
    def get_cheapest_models(self, limit: int = 5) -> List[Model]:
        """Get the cheapest models"""
        sorted_models = sorted(
            self.models.values(),
            key=lambda m: m.pricing.get_avg_cost_per_1k_tokens()
        )
        return sorted_models[:limit]
    
    def get_models_under_cost(self, max_cost_per_1k: float) -> List[Model]:
        """Get models under a cost threshold"""
        return [
            m for m in self.models.values()
            if m.pricing.get_avg_cost_per_1k_tokens() <= max_cost_per_1k
        ]
    
    def find_fallback_models(self, current_model_id: str, max_fallbacks: int = 3) -> List[str]:
        """Find cheaper fallback models for a given model"""
        current_model = self.get_model(current_model_id)
        if not current_model:
            return []
        
        # Find models that are cheaper and from same provider (preferred)
        same_provider_cheaper = [
            m for m in self.models.values()
            if (m.info.provider == current_model.info.provider and
                m.is_cheaper_than(current_model) and
                m.is_enabled and not m.is_deprecated)
        ]
        
        # Find any cheaper models if not enough from same provider
        all_cheaper = [
            m for m in self.models.values()
            if (m.is_cheaper_than(current_model) and
                m.is_enabled and not m.is_deprecated)
        ]
        
        # Sort by cost and take the best options
        same_provider_cheaper.sort(key=lambda m: m.pricing.get_avg_cost_per_1k_tokens())
        all_cheaper.sort(key=lambda m: m.pricing.get_avg_cost_per_1k_tokens())
        
        # Prefer same provider, then fill with others
        fallbacks = same_provider_cheaper[:max_fallbacks]
        if len(fallbacks) < max_fallbacks:
            remaining = max_fallbacks - len(fallbacks)
            other_models = [m for m in all_cheaper if m not in fallbacks]
            fallbacks.extend(other_models[:remaining])
        
        return [m.info.model_id for m in fallbacks]
    
    def get_model_comparison(self, model_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple models"""
        models = [self.get_model(mid) for mid in model_ids if self.get_model(mid)]
        
        if not models:
            return {}
        
        return {
            "models": [
                {
                    "model_id": m.info.model_id,
                    "name": m.info.name,
                    "provider": m.info.provider.value,
                    "tier": m.get_tier().value,
                    "avg_cost_per_1k": m.pricing.get_avg_cost_per_1k_tokens(),
                    "context_length": m.info.context_length,
                    "total_usage_cost": m.performance.total_cost_usd,
                    "success_rate": m.performance.success_rate
                }
                for m in models
            ],
            "cheapest": min(models, key=lambda m: m.pricing.get_avg_cost_per_1k_tokens()).info.model_id,
            "most_expensive": max(models, key=lambda m: m.pricing.get_avg_cost_per_1k_tokens()).info.model_id
        }


# ---------- 6. Budget Policy Integration ----------
class ModelBudgetPolicy(BaseModel):
    """Policy for model selection based on budget constraints"""
    model_config = ConfigDict(validate_assignment=True)
    
    monthly_budget_usd: float = 1000.0
    current_spend_usd: float = 0.0
    
    # Budget thresholds for different tiers
    budget_thresholds: Dict[float, ModelTier] = Field(default_factory=lambda: {
        0.5: ModelTier.PREMIUM,    # < 50% budget: Use premium models
        0.7: ModelTier.BALANCED,   # < 70% budget: Use balanced models
        0.8: ModelTier.EFFICIENT,  # < 80% budget: Use efficient models (PRD requirement)
        1.0: ModelTier.BUDGET      # < 100% budget: Use budget models
    })
    
    def __init__(self, **data):
        super().__init__(**data)
        # Ensure budget thresholds are sorted
        self.budget_thresholds = dict(sorted(self.budget_thresholds.items()))
    
    def get_spend_ratio(self) -> float:
        """Get current spend ratio"""
        return self.current_spend_usd / self.monthly_budget_usd
    
    def get_recommended_tier(self) -> ModelTier:
        """Get recommended model tier based on current spend"""
        spend_ratio = self.get_spend_ratio()
        
        for threshold, tier in self.budget_thresholds.items():
            if spend_ratio <= threshold:
                return tier
        
        return ModelTier.BUDGET  # Default to budget if over 100%
    
    def select_model(self, preferred_model_id: str, registry: ModelRegistry) -> tuple[str, str]:
        """
        Select appropriate model based on budget policy.
        Returns (selected_model_id, reason)
        """
        preferred_model = registry.get_model(preferred_model_id)
        if not preferred_model:
            return preferred_model_id, "Preferred model not found"
        
        spend_ratio = self.get_spend_ratio()
        recommended_tier = self.get_recommended_tier()
        preferred_tier = preferred_model.get_tier()
        
        # If under 50% budget, use preferred model
        if spend_ratio <= 0.5:
            return preferred_model_id, "Budget healthy - using preferred model"
        
        # If preferred model is already in recommended tier or cheaper
        if (preferred_tier == recommended_tier or 
            preferred_tier.value in ['efficient', 'budget'] and recommended_tier == ModelTier.PREMIUM):
            return preferred_model_id, f"Preferred model fits {recommended_tier.value} tier"
        
        # Need to find a cheaper alternative
        fallback_models = registry.find_fallback_models(preferred_model_id, max_fallbacks=5)
        
        # Find best model in recommended tier
        for fallback_id in fallback_models:
            fallback_model = registry.get_model(fallback_id)
            if fallback_model and fallback_model.get_tier() == recommended_tier:
                savings = ((preferred_model.pricing.get_avg_cost_per_1k_tokens() - 
                          fallback_model.pricing.get_avg_cost_per_1k_tokens()) / 
                         preferred_model.pricing.get_avg_cost_per_1k_tokens()) * 100
                
                return fallback_id, f"Budget at {spend_ratio:.1%} - switched to {recommended_tier.value} tier (saves {savings:.0f}%)"
        
        # If no exact tier match, use cheapest fallback
        if fallback_models:
            cheapest_id = fallback_models[0]  # Already sorted by cost
            cheapest_model = registry.get_model(cheapest_id)
            if cheapest_model:
                savings = ((preferred_model.pricing.get_avg_cost_per_1k_tokens() - 
                          cheapest_model.pricing.get_avg_cost_per_1k_tokens()) / 
                         preferred_model.pricing.get_avg_cost_per_1k_tokens()) * 100
                
                return cheapest_id, f"Budget at {spend_ratio:.1%} - using cheapest available (saves {savings:.0f}%)"
        
        # No alternatives found
        return preferred_model_id, f"No cheaper alternatives found for {preferred_model_id}"


# ---------- Usage Example ----------
if __name__ == "__main__":
    # Load models from OpenRouter data
    registry = ModelRegistry.load_from_openrouter_json("openrouter_pricing_converted.json")
    
    # Set up budget policy
    policy = ModelBudgetPolicy(monthly_budget_usd=1000.0, current_spend_usd=850.0)  # 85% used
    
    # Policy decision for model selection
    selected_model, reason = policy.select_model("google/gemini-2.5-pro", registry)
    print(f"Selected: {selected_model}")
    print(f"Reason: {reason}")
    
    # Get model comparison
    comparison = registry.get_model_comparison([
        "google/gemini-2.5-pro",
        "google/gemini-2.5-flash", 
        "openai/gpt-4o-mini"
    ])
    print(f"Comparison: {comparison}")