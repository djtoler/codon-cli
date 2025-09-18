# File: saop/templates/base_agent/models/agent_model.py

from __future__ import annotations
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from enum import Enum
import uuid
from utils import ComplianceZone

class AgentStatus(Enum):
    """Current operational status of an agent"""
    ACTIVE = "active"
    IDLE = "idle"
    ERROR = "error"
    BUDGET_EXCEEDED = "budget_exceeded"


class AgentModel(BaseModel):
    """Simplified agent model focused on PRD requirements"""
    model_config = ConfigDict(extra="forbid")
    
    # Identity
    agent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role_name: str
    status: AgentStatus = AgentStatus.IDLE
    
    # PRD Requirement: p95 latency < 2s
    p95_response_time_ms: float = 0.0
    avg_response_time_ms: float = 0.0
    
    # PRD Requirement: Cost tracking and dashboard
    total_cost_usd: float = 0.0
    monthly_cost_usd: float = 0.0
    
    # PRD Requirement: Budget > 80% threshold
    monthly_budget_limit_usd: float = 300.0
    monthly_spend_ratio: float = 0.0  # monthly_cost / budget_limit
    
    # PRD Requirement: Cache hit/miss metrics
    cache_hit_rate: float = 0.0
    total_interactions: int = 0
    
    # PRD Requirement: Compliance zones
    compliance_zone: ComplianceZone = ComplianceZone.GENERAL
    
    # Basic tracking
    current_tools: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Response time history for percentile calculation
    _response_times: List[float] = Field(default_factory=list, exclude=True)
    
    def update_metrics(self, response_time_ms: float, cost_usd: float, 
                      success: bool, cache_hit: bool = False) -> None:
        """Update metrics after interaction - PRD requirements only"""
        
        # Update interaction count
        self.total_interactions += 1
        
        # Update cost (PRD: cost dashboard)
        self.total_cost_usd += cost_usd
        self.monthly_cost_usd += cost_usd
        self.monthly_spend_ratio = self.monthly_cost_usd / self.monthly_budget_limit_usd
        
        # Update latency (PRD: p95 < 2s requirement)
        self._response_times.append(response_time_ms)
        if len(self._response_times) > 100:  # Keep last 100 for calculation
            self._response_times = self._response_times[-100:]
        
        # Calculate percentiles
        if self._response_times:
            sorted_times = sorted(self._response_times)
            n = len(sorted_times)
            self.avg_response_time_ms = sum(sorted_times) / n
            self.p95_response_time_ms = sorted_times[int(n * 0.95)]
        
        # Update cache metrics (PRD: cache hit/miss)
        if hasattr(self, '_cache_interactions'):
            self._cache_interactions += 1
            if cache_hit:
                self._cache_hits += 1
        else:
            self._cache_interactions = 1
            self._cache_hits = 1 if cache_hit else 0
        
        self.cache_hit_rate = self._cache_hits / self._cache_interactions
        
        # Update status based on budget (PRD: 80% threshold)
        if self.monthly_spend_ratio > 1.0:
            self.status = AgentStatus.BUDGET_EXCEEDED
        elif self.status == AgentStatus.BUDGET_EXCEEDED and self.monthly_spend_ratio <= 1.0:
            self.status = AgentStatus.ACTIVE
        
        self.updated_at = datetime.utcnow()
    
    def needs_budget_optimization(self) -> bool:
        """PRD requirement: trigger at 80% budget"""
        return self.monthly_spend_ratio > 0.8
    
    def exceeds_latency_slo(self, slo_ms: int = 2000) -> bool:
        """PRD requirement: p95 < 2s"""
        return self.p95_response_time_ms > slo_ms
    
    def to_redis_dict(self) -> Dict[str, Any]:
        """Minimal Redis storage"""
        return {
            "agent_id": self.agent_id,
            "role_name": self.role_name,
            "status": self.status.value,
            "monthly_cost_usd": self.monthly_cost_usd,
            "monthly_spend_ratio": self.monthly_spend_ratio,
            "p95_response_time_ms": self.p95_response_time_ms,
            "cache_hit_rate": self.cache_hit_rate,
            "compliance_zone": self.compliance_zone.value,
            "updated_at": self.updated_at.isoformat()
        }
    
    @classmethod
    def from_redis_dict(cls, data: Dict[str, Any]) -> "AgentModel":
        """Load from Redis"""
        if "status" in data:
            data["status"] = AgentStatus(data["status"])
        if "compliance_zone" in data:
            data["compliance_zone"] = ComplianceZone(data["compliance_zone"])
        if "updated_at" in data:
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        return cls(**data)


