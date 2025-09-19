"""
Simple Policy Configuration Loader for SAOP
Loads YAML policy configuration and provides validation.
Pure validator - all values must come from YAML file.
"""

import yaml
import os
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
import logging

log = logging.getLogger("policy_config")


class ModelPolicy(BaseModel):
    """Model selection policy configuration - values from YAML"""
    expensive: str
    standard: str  
    cheap: str
    budget_rules: List[Dict[str, Any]]


class ComplianceRule(BaseModel):
    """Tool compliance rule"""
    description: str
    blocked_tools: List[str] = []
    allowed_tools: List[str] = []


class ToolPolicy(BaseModel):
    """Tool access control policy - values from YAML"""
    compliance_rules: Dict[str, ComplianceRule]
    role_policies: Dict[str, Dict[str, str]]


class BudgetPolicy(BaseModel):
    """Budget and cost cap configuration - values from YAML"""
    role_limits: Dict[str, float]


class CompliancePolicy(BaseModel):
    """Compliance and audit configuration - values from YAML"""
    data_retention_years: int
    require_audit_logs: bool
    phi_pii_tags: List[str]
    sensitive_data_roles: List[str]


class OperationsPolicy(BaseModel):
    """Operational settings for policy engine - values from YAML"""
    decision_cache_ttl_seconds: int
    max_cache_size: int
    max_tools_per_execution: int
    tool_timeout_seconds: int


class SystemPolicy(BaseModel):
    """System-wide configuration settings - values from YAML"""
    monthly_budget_usd: float
    budget_warning_threshold: float
    emergency_budget_threshold: float
    default_slo_ms: int
    max_execution_time_ms: int
    active_role: Optional[str] = None  # Only optional field


class MainAgentRole(BaseModel):
    """Define the main agent role for the system - single source of truth"""
    name: str
    system_prompt: str = "You are a helpful assistant."
    tools: List[str] = Field(default_factory=list)
    tool_bundles: List[str] = Field(default_factory=list)
    model: Dict[str, Any] = Field(default_factory=dict)  # Simplified model config
    response_format: Optional[str] = None
    human_review: bool = False
    observability: Dict[str, Any] = Field(default_factory=dict)
    guardrails: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # Backward compatibility methods for existing LangGraph code
    def get(self, key: str, default=None):
        """Dict-like access for backward compatibility"""
        return getattr(self, key, default)
    
    def __getitem__(self, key: str):
        """Dict-like access with [] syntax"""
        if hasattr(self, key):
            return getattr(self, key)
        raise KeyError(f"'{key}' not found in MainAgentRole")
    
    def __contains__(self, key: str):
        """Dict-like 'in' operator"""
        return hasattr(self, key)
    
    def keys(self):
        """Dict-like keys() method"""
        return self.model_fields.keys()
    
    def items(self):
        """Dict-like items() method"""
        return [(k, getattr(self, k)) for k in self.model_fields.keys()]
    
    def values(self):
        """Dict-like values() method"""
        return [getattr(self, k) for k in self.model_fields.keys()]
    
    def to_dict(self) -> dict:
        """Convert to plain dictionary"""
        return self.model_dump()
    
    def __iter__(self):
        """Make iterable like a dict"""
        return iter(self.model_fields.keys())


# Updated PolicyConfig class
class PolicyConfig(BaseModel):
    """Main policy configuration - now includes main agent role"""
    version: str
    system: SystemPolicy
    models: ModelPolicy
    tools: ToolPolicy  
    budgets: BudgetPolicy
    compliance: CompliancePolicy
    operations: OperationsPolicy
    main_agent: MainAgentRole  # NEW: Single source of truth for agent role

def load_policy_config(config_path: str = "config/policy/policy.yaml") -> PolicyConfig:
    """
    Load and validate policy configuration from YAML file.
    All values must be provided in YAML - no defaults.
    """
    
    # Find config file
    if not os.path.exists(config_path):
        # Try alternative locations
        alt_paths = [
            "policy_config.yaml",
            "../config/policy/policy.yaml" 
        ]
        for alt_path in alt_paths:
            if os.path.exists(alt_path):
                config_path = alt_path
                break
        else:
            raise FileNotFoundError(f"Policy config file not found: {config_path}")
    
    # Load YAML
    try:
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
            
        if not raw_config:
            raise ValueError("Policy config file is empty")
            
        log.info(f"Loaded policy config from: {config_path}")
        
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML in policy config: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load policy config: {e}")
    
    # Convert compliance rules to objects
    if "tools" in raw_config and "compliance_rules" in raw_config["tools"]:
        compliance_rules = {}
        for name, rule_data in raw_config["tools"]["compliance_rules"].items():
            compliance_rules[name] = ComplianceRule(**rule_data)
        raw_config["tools"]["compliance_rules"] = compliance_rules
    
    # Validate and create config object - will fail if YAML is incomplete
    try:
        config = PolicyConfig(**raw_config)
        log.info(f"Policy config validated successfully (version: {config.version})")
        _log_config_summary(config)
        return config
        
    except Exception as e:
        log.error(f"Policy config validation failed: {e}")
        log.error("All configuration values must be provided in YAML file")
        raise


def _log_config_summary(config: PolicyConfig):
    """Log summary of validated configuration"""
    log.info("=== POLICY CONFIG VALIDATION ===")
    log.info(f"Version: {config.version}")
    log.info(f"System budget: ${config.system.monthly_budget_usd:.2f}")
    log.info(f"Budget warning: {config.system.budget_warning_threshold:.1%}")
    log.info(f"Emergency threshold: {config.system.emergency_budget_threshold:.1%}")
    log.info(f"Active role: {config.system.active_role or 'None'}")
    log.info(f"Models defined: {config.models.expensive}, {config.models.standard}, {config.models.cheap}")
    log.info(f"Budget rules: {len(config.models.budget_rules)}")
    log.info(f"Compliance rules: {list(config.tools.compliance_rules.keys())}")
    log.info(f"Role policies: {list(config.tools.role_policies.keys())}")
    log.info(f"Role budgets: {len(config.budgets.role_limits)}")
    log.info("=" * 33)


# Global config cache
_config_cache: Optional[PolicyConfig] = None


def get_policy_config() -> PolicyConfig:
    """Get the global policy configuration (cached)"""
    global _config_cache
    
    if _config_cache is None:
        _config_cache = load_policy_config()
    
    return _config_cache


def reload_policy_config() -> PolicyConfig:
    """Reload the policy configuration from file"""
    global _config_cache
    _config_cache = load_policy_config()
    return _config_cache


def validate_policy_config_file(config_path: str = "config/policy/policy.yaml") -> List[str]:
    """Validate policy configuration file and return any errors"""
    errors = []
    
    try:
        load_policy_config(config_path)
        log.info("Policy configuration validation passed")
        
    except FileNotFoundError as e:
        errors.append(f"Config file not found: {e}")
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML: {e}")
    except Exception as e:
        errors.append(f"Validation error: {e}")
            
    return errors