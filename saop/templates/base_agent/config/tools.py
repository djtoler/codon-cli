# File: saop/templates/base_agent/models/tool_model.py
from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict, computed_field
from datetime import datetime
from enum import Enum
import uuid
import json
from .utils import ComplianceZone


# The Enum (for fixed choices) remains the same
class ToolCategory(Enum):
    """A fixed set of cost categories."""
    FREE = "free"
    CHEAP = "cheap"
    MODERATE = "moderate"
    EXPENSIVE = "expensive"

# Fix the ToolType - should be an Enum
class ToolType(Enum):
    """Determines if a tool is deterministic or not."""
    DETERMINISTIC = "deterministic"
    NON_DETERMINISTIC = "non_deterministic"

# Pydantic Models (for variable data)
class ToolInfo(BaseModel):
    """Contains the name and description of a tool."""
    name: str = ""
    description: str = ""

class ToolBundles(BaseModel):
    """A container for a list of tool bundle tags."""
    bundles: List[str] = Field(default_factory=list)

class ToolLatency(BaseModel):
    """Tracks latency metrics for a tool."""
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0

class ToolCache(BaseModel):
    """Describes the caching behavior of a tool."""
    cache_hit_rate: float = 0.0

class ToolCost(BaseModel):
    """Represents and tracks the usage cost of a single tool."""
    cost_per_call: float
    total_cost_usd: float = 0.0
    monthly_cost_usd: float = 0.0
    call_count: int = 0
    
    @computed_field
    @property
    def category(self) -> str:
        """Determines the category from the cost per call."""
        if self.cost_per_call == 0.0:
            return ToolCategory.FREE.value
        if self.cost_per_call < 0.02:
            return ToolCategory.CHEAP.value
        if self.cost_per_call <= 0.05:
            return ToolCategory.MODERATE.value
        return ToolCategory.EXPENSIVE.value
    
    def log_call(self, num_calls: int = 1):
        """Records one or more tool calls and updates total costs."""
        cost_of_calls = self.cost_per_call * num_calls
        self.call_count += num_calls
        self.total_cost_usd += cost_of_calls
        self.monthly_cost_usd += cost_of_calls

class ToolTags(BaseModel):
    tags: List[str] = Field(default_factory=list)



# Main ToolModel class that combines everything
class ToolModel(BaseModel):
    """Complete model representing a tool with all its properties and metrics."""
    
    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
        use_enum_values=True
    )
    
    # Core identification
    tool_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Tool information
    info: ToolInfo = Field(default_factory=ToolInfo)
    tool_type: ToolType = ToolType.DETERMINISTIC
    tool_tags: ToolTags = Field(default_factory=ToolTags)
    
    # Organization and categorization  
    bundles: ToolBundles = Field(default_factory=ToolBundles)
    compliance_zone: Optional[ComplianceZone] = None
    
    # Performance metrics
    latency: ToolLatency = Field(default_factory=ToolLatency)
    cache: ToolCache = Field(default_factory=ToolCache)
    
    # Cost tracking
    cost: ToolCost
    
    # Status and configuration
    is_active: bool = True
    is_deprecated: bool = False
    version: str = "1.0.0"
    
    # Additional metadata
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    @computed_field
    @property 
    def cost_category(self) -> str:
        """Get the cost category from the embedded ToolCost."""
        return self.cost.category
    
    @computed_field
    @property
    def is_free(self) -> bool:
        """Check if this tool is in the FREE cost category."""
        return self.cost_category == ToolCategory.FREE.value
    
    @computed_field
    @property
    def performance_score(self) -> float:
        """Calculate a performance score based on latency and cache hit rate."""
        # Lower latency is better, higher cache hit rate is better
        if self.latency.avg_latency_ms == 0:
            latency_score = 1.0
        else:
            latency_score = max(0.1, 1.0 / (1.0 + self.latency.avg_latency_ms / 1000))
        
        cache_score = self.cache.cache_hit_rate
        
        return (latency_score + cache_score) / 2.0
    
    def log_usage(self, num_calls: int = 1, latency_ms: Optional[float] = None):
        """Log tool usage and optionally update latency metrics."""
        # Update cost tracking
        self.cost.log_call(num_calls)
        
        # Update latency if provided
        if latency_ms is not None:
            # Simple moving average update
            total_calls = self.cost.call_count
            if total_calls == 1:
                self.latency.avg_latency_ms = latency_ms
            else:
                self.latency.avg_latency_ms = (
                    (self.latency.avg_latency_ms * (total_calls - 1) + latency_ms) / total_calls
                )
        
        # Update timestamp
        self.updated_at = datetime.utcnow()
    
    def add_to_bundle(self, bundle_name: str):
        """Add this tool to a bundle."""
        if bundle_name not in self.bundles.bundles:
            self.bundles.bundles.append(bundle_name)
            self.updated_at = datetime.utcnow()
    
    def remove_from_bundle(self, bundle_name: str):
        """Remove this tool from a bundle."""
        if bundle_name in self.bundles.bundles:
            self.bundles.bundles.remove(bundle_name)
            self.updated_at = datetime.utcnow()
    
    def deprecate(self):
        """Mark this tool as deprecated and inactive."""
        self.is_deprecated = True
        self.is_active = False
        self.updated_at = datetime.utcnow()
    
    def to_summary_dict(self) -> Dict[str, Any]:
        """Return a summary dictionary for logging or display."""
        return {
            "tool_name": self.info.name,
            "tool_tags": self.tool_tags,
            "tool_type": self.tool_type.value,
            "tool_cost_category": self.cost_category,
            "tool_total_calls": self.cost.call_count,
            "tool_total_cost_usd": self.cost.total_cost_usd,
            "tool_performance_score": self.performance_score,
            "tool_is_active": self.is_active,
            "tool_bundles": self.bundles.bundles
        }
    
