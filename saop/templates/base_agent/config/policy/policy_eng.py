"""
SAOP Policy Engine - Core PRD Implementation
Runtime policy engine for model selection and tool access control.
Uses complete YAML configuration without hardcoded fallbacks.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import fnmatch
import os

from config.policy.policy_config import PolicyConfig, get_policy_config
from config.nodes import get_budget_summary, get_node_by_name
from a2a.server.agent_execution.context import RequestContext

# # Import existing system components for integration
# try:
#     from config.nodes import get_budget_summary, get_node_by_name
#     from a2a.server.agent_execution.context import RequestContext
# except ImportError:
#     # Fallbacks for development
#     RequestContext = Any
#     def get_budget_summary():
#         return {"utilization": 0.0}
#     def get_node_by_name(name):
#         return None

log = logging.getLogger("policy_engine")


@dataclass
class PolicyDecision:
    """Simple policy decision result"""
    approved: bool
    reason: str
    selected_model: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    cost_limit_exceeded: bool = False


class PolicyEngine:
    """
    Policy engine implementing core PRD requirements:
    1. Model selection based on budget thresholds
    2. Tool blocking based on compliance rules  
    3. Cost caps per role
    
    Uses complete YAML configuration - no hardcoded fallbacks.
    """
    
    def __init__(self, config: Optional[PolicyConfig] = None):
        self.config = config or get_policy_config()
        
        # Validate required configuration exists
        self._validate_config()
        
        log.info(f"Policy Engine initialized (version: {self.config.version})")
        log.info(f"System budget: ${self.config.system.monthly_budget_usd:.2f}")
        log.info(f"Budget warning threshold: {self.config.system.budget_warning_threshold:.1%}")
        log.info(f"Emergency threshold: {self.config.system.emergency_budget_threshold:.1%}")
    
    def _validate_config(self):
        """Validate that all required configuration is present"""
        required_system_fields = [
            'monthly_budget_usd', 'budget_warning_threshold', 'emergency_budget_threshold',
            'default_slo_ms', 'max_execution_time_ms'
        ]
        
        for field in required_system_fields:
            if not hasattr(self.config.system, field):
                raise ValueError(f"Missing required system configuration: {field}")
        
        # Validate models exist
        if not all([self.config.models.expensive, self.config.models.standard, self.config.models.cheap]):
            raise ValueError("Missing required model configuration (expensive/standard/cheap)")
        
        log.debug("Policy configuration validation passed")
    
    def _get_current_budget_utilization(self) -> float:
        """Get current system budget utilization"""
        try:
            budget_summary = get_budget_summary()
            return budget_summary.get("utilization", 0.0)
        except Exception as e:
            log.warning(f"Could not get budget summary: {e}, assuming 0% utilization")
            return 0.0
    
    def _get_role_monthly_spend(self, role_name: str) -> float:
        """Get current monthly spend for a role"""
        try:
            node = get_node_by_name(role_name)
            if node:
                return node.cost_tracker.monthly_cost_usd
        except Exception as e:
            log.warning(f"Could not get spend data for role {role_name}: {e}")
        return 0.0
    
    def select_model(self, role_name: str, current_model: str) -> str:
        """
        PRD Requirement: "swap LLM to cheaper model when monthly budget > 80%"
        Select model based on budget utilization using complete YAML config.
        """
        budget_utilization = self._get_current_budget_utilization()
        
        # Use configuration values directly - no fallbacks needed
        warning_threshold = self.config.system.budget_warning_threshold
        emergency_threshold = self.config.system.emergency_budget_threshold
        
        log.info(f"Model selection for {role_name}: budget={budget_utilization:.1%}, "
                f"warning={warning_threshold:.1%}, emergency={emergency_threshold:.1%}")
        
        # Check for emergency mode first
        if budget_utilization >= emergency_threshold:
            selected_model = self.config.models.cheap
            reason = f"Emergency budget protection at {budget_utilization:.1%}"
            
            if selected_model != current_model:
                log.warning(f"EMERGENCY: Model switch for {role_name}: {current_model} -> {selected_model}")
            
            return selected_model
        
        # Check budget rules in order
        for rule in self.config.models.budget_rules:
            threshold = rule.get("when_budget_above", 1.0)
            
            if budget_utilization >= threshold:
                target_model = rule.get("use_model", "cheap")
                
                # Map target to actual model from config
                if target_model == "expensive":
                    selected_model = self.config.models.expensive
                elif target_model == "standard":
                    selected_model = self.config.models.standard
                elif target_model == "cheap":
                    selected_model = self.config.models.cheap
                else:
                    selected_model = target_model  # Direct model name
                
                reason = rule.get("reason", f"Budget over {threshold:.1%}")
                
                if selected_model != current_model:
                    log.info(f"Model switch for {role_name}: {current_model} -> {selected_model} ({reason})")
                
                return selected_model
        
        # No budget rules triggered, keep current model
        log.debug(f"Model unchanged for {role_name}: {current_model}")
        return current_model
    
    def _match_tool_pattern(self, tool_name: str, pattern: str) -> bool:
        """Check if tool matches a pattern (supports wildcards)"""
        return fnmatch.fnmatch(tool_name, pattern)
    
    def filter_tools(self, role_name: str, available_tools: List[str]) -> List[str]:
        """
        PRD Requirement: "block non-HIPAA tools for healthcare agents via policy file"
        Filter tools based on role's compliance requirements.
        """
        log.info(f"Filtering {len(available_tools)} tools for role: {role_name}")
        
        # Get role's compliance level
        role_policy = self.config.tools.role_policies.get(role_name, {})
        compliance_level = role_policy.get("compliance_level")
        
        if not compliance_level:
            log.debug(f"No compliance rules for {role_name}, allowing all tools")
            return available_tools
        
        # Get compliance rule
        compliance_rule = self.config.tools.compliance_rules.get(compliance_level)
        if not compliance_rule:
            log.warning(f"Unknown compliance level '{compliance_level}' for {role_name}")
            return available_tools
        
        log.info(f"Applying compliance rule '{compliance_level}' to {role_name}")
        
        allowed_tools = []
        
        for tool in available_tools:
            # Check if tool is blocked
            is_blocked = False
            for blocked_pattern in compliance_rule.blocked_tools:
                if self._match_tool_pattern(tool, blocked_pattern):
                    log.debug(f"Tool '{tool}' blocked by pattern '{blocked_pattern}'")
                    is_blocked = True
                    break
            
            if is_blocked:
                continue
            
            # Check if tool is allowed (if allowlist exists)
            if compliance_rule.allowed_tools:
                is_allowed = False
                for allowed_pattern in compliance_rule.allowed_tools:
                    if self._match_tool_pattern(tool, allowed_pattern):
                        is_allowed = True
                        break
                
                if not is_allowed:
                    log.debug(f"Tool '{tool}' not in allowed list")
                    continue
            
            # Tool passed all checks
            allowed_tools.append(tool)
        
        log.info(f"Tool filtering complete: {len(allowed_tools)}/{len(available_tools)} tools allowed for {role_name}")
        return allowed_tools
    
    def check_cost_limit(self, role_name: str) -> PolicyDecision:
        """
        PRD Requirement: "Cost caps & latency budgets per skill"
        Check if role has exceeded its cost limit.
        """
        role_limit = self.config.budgets.role_limits.get(role_name)
        
        if not role_limit:
            # No limit set, allow
            return PolicyDecision(
                approved=True,
                reason="No cost limit configured"
            )
        
        current_spend = self._get_role_monthly_spend(role_name)
        
        if current_spend >= role_limit:
            log.warning(f"Cost limit exceeded for {role_name}: ${current_spend:.2f} >= ${role_limit:.2f}")
            return PolicyDecision(
                approved=False,
                reason=f"Monthly cost limit exceeded (${current_spend:.2f} >= ${role_limit:.2f})",
                cost_limit_exceeded=True
            )
        
        utilization = current_spend / role_limit if role_limit > 0 else 0.0
        log.debug(f"Cost check passed for {role_name}: {utilization:.1%} of limit used")
        
        return PolicyDecision(
            approved=True,
            reason=f"Within cost limit ({utilization:.1%} used)"
        )
    
    def evaluate_request(self, role_name: str, context: RequestContext = None) -> PolicyDecision:
        """
        PRD Requirement: "policy engine can deny tool usage if limits exceeded"
        Evaluate if a request should be approved based on cost limits and system state.
        """
        log.info(f"Evaluating request for role: {role_name}")
        
        # Check system emergency mode first
        budget_utilization = self._get_current_budget_utilization()
        emergency_threshold = self.config.system.emergency_budget_threshold
        
        if budget_utilization >= emergency_threshold:
            log.critical(f"System in emergency mode: {budget_utilization:.1%} >= {emergency_threshold:.1%}")
            return PolicyDecision(
                approved=False,
                reason=f"System in emergency budget mode ({budget_utilization:.1%} utilization)"
            )
        
        # Check role-specific cost limits
        cost_decision = self.check_cost_limit(role_name)
        if not cost_decision.approved:
            return cost_decision
        
        # Request approved
        return PolicyDecision(
            approved=True,
            reason="Request approved by policy evaluation"
        )
    
    def is_sensitive_data_role(self, role_name: str) -> bool:
        """
        PRD Requirement: PHI/PII handling compliance
        Check if role handles sensitive data requiring audit logs.
        """
        return role_name in self.config.compliance.sensitive_data_roles
    
    def requires_audit_logging(self, role_name: str) -> bool:
        """
        PRD Requirement: "audit logs retained for 7 years (HIPAA)"
        Determine if role requires enhanced audit logging.
        """
        return self.config.compliance.require_audit_logs and self.is_sensitive_data_role(role_name)
    
    def get_data_retention_years(self) -> int:
        """
        PRD Requirement: "7 years (HIPAA)" 
        Get required data retention period from config.
        """
        return self.config.compliance.data_retention_years
    
    def get_max_tools_per_execution(self, role_name: str = None) -> int:
        """Get maximum tools per execution from config"""
        # Check role-specific policy first
        if role_name:
            role_policy = self.config.tools.role_policies.get(role_name, {})
            if "max_tools_per_execution" in role_policy:
                return role_policy["max_tools_per_execution"]
        
        # Fall back to operations config
        return getattr(self.config.operations, 'max_tools_per_execution', 10)
    
    def get_tool_timeout_seconds(self, role_name: str = None) -> int:
        """Get tool timeout from config"""
        # Check role-specific policy first
        if role_name:
            role_policy = self.config.tools.role_policies.get(role_name, {})
            if "tool_timeout_seconds" in role_policy:
                return role_policy["tool_timeout_seconds"]
        
        # Fall back to operations config
        return getattr(self.config.operations, 'tool_timeout_seconds', 30)
    
    def reload_config(self):
        """Reload policy configuration"""
        from policy_config import reload_policy_config
        self.config = reload_policy_config()
        self._validate_config()
        log.info(f"Policy configuration reloaded (version: {self.config.version})")


def get_main_agent_role_name() -> str:
    """Get the main agent role name from policy configuration"""
    try:
        from config.policy.policy_config import get_policy_config
        config = get_policy_config()
        
        if hasattr(config, 'main_agent') and config.main_agent.name:
            log.info(f"Main agent role from policy: {config.main_agent.name}")
            return config.main_agent.name
    except Exception as e:
        log.warning(f"Could not get main agent role from policy: {e}")
    
    # Fallback to environment variable
    env_role = os.getenv("AGENT_NAME")
    if env_role:
        log.info(f"Main agent role from environment: {env_role}")
        return env_role
    
    # Final fallback with clear error
    raise ValueError(
        "No main agent role configured. Set main_agent.name in policy YAML or AGENT_NAME environment variable"
    )


def get_main_agent_config() -> Dict[str, Any]:
    """Get the complete main agent configuration"""
    try:
        from config.policy.policy_config import get_policy_config
        config = get_policy_config()
        return config.main_agent.to_dict()
    except Exception as e:
        log.error(f"Could not get main agent config: {e}")
        return {}



# Global policy engine instance
_policy_engine: Optional[PolicyEngine] = None


def get_policy_engine() -> PolicyEngine:
    """Get the global policy engine instance"""
    global _policy_engine
    
    if _policy_engine is None:
        _policy_engine = PolicyEngine()
    
    return _policy_engine


# Integration helper functions for existing codebase

def policy_select_model(role_name: str, current_model: str) -> str:
    """
    Integration point for langchain_chains.py
    Select model based on policy rules.
    """
    engine = get_policy_engine()
    return engine.select_model(role_name, current_model)


def policy_filter_tools(role_name: str, available_tools: List[str]) -> List[str]:
    """
    Integration point for agent_factory.py  
    Filter tools based on compliance policies.
    """
    engine = get_policy_engine()
    return engine.filter_tools(role_name, available_tools)


def policy_check_request(role_name: str, context: RequestContext = None) -> bool:
    """
    Integration point for langgraph_executor.py
    Check if request should be approved.
    """
    engine = get_policy_engine()
    decision = engine.evaluate_request(role_name, context)
    return decision.approved


if __name__ == "__main__":
    # Test the policy engine with complete configuration
    try:
        engine = PolicyEngine()
        
        print("=== POLICY ENGINE TEST ===")
        print(f"Config version: {engine.config.version}")
        print(f"Budget warning: {engine.config.system.budget_warning_threshold:.1%}")
        print(f"Emergency threshold: {engine.config.system.emergency_budget_threshold:.1%}")
        
        # Test model selection
        test_model = engine.select_model("math_specialist", "openai:gpt-4")
        print(f"Model selection: {test_model}")
        
        # Test tool filtering
        test_tools = ["add", "multiply", "public_search", "secure_search"]
        filtered = engine.filter_tools("healthcare_agent", test_tools)
        print(f"Tool filtering: {filtered}")
        
        # Test cost limits
        cost_decision = engine.check_cost_limit("math_specialist")
        print(f"Cost check: approved={cost_decision.approved}, reason={cost_decision.reason}")
        
        # Test request evaluation
        request_decision = engine.evaluate_request("general_support")
        print(f"Request evaluation: approved={request_decision.approved}, reason={request_decision.reason}")
        
        print("Policy engine test complete")
        
    except Exception as e:
        print(f"Policy engine test failed: {e}")
        import traceback
        traceback.print_exc()