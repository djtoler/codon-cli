# vars.py
"""
Central repository for reusable prompt components and variables,
all defined as Enum classes for consistent access.
"""

from enum import Enum

class ToolUsageMode(str, Enum):
    """Defines the modes for tool usage policies."""
    MANDATORY = "mandatory"
    PREFERRED = "preferred"
    OPTIONAL = "optional"
    DISCOURAGED = "discouraged"

class CommunicationStyle(str, Enum):
    """Defines the communication styles for prompts."""
    PROFESSIONAL = "professional"
    FRIENDLY = "friendly"

class ToolPromptVars(str, Enum):
    """Prompt variables for tool usage directives."""
    
    MANDATORY = """
    <tool_usage_policy>
        CRITICAL: You MUST use available tools for ANY operations they can handle. 
        NEVER perform manual calculations, lookups, or operations when tools exist.
        Tool usage is MANDATORY, not optional.
    </tool_usage_policy>
    <tool_workflow>
        1. FIRST: Check if you have a relevant tool
        2. ALWAYS: Use the tool instead of manual work
        3. THEN: Present the tool result to the user
        4. FINALLY: Explain what the tool did
    </tool_workflow>
    """
    
    PREFERRED = """
    <tool_usage_policy>
        STRONGLY PREFER using available tools over manual work.
        Use tools whenever possible for accuracy and demonstration.
        Only skip tools if the operation is trivial or the tool doesn't fit.
    </tool_usage_policy>
    <tool_workflow>
        1. Consider if you have a relevant tool
        2. Prefer using the tool when available
    </tool_workflow>
    """
    
    OPTIONAL = """
    <tool_usage_policy>
        Use tools when they add value or accuracy.
        Balance between tool usage and direct responses.
        Choose the most efficient approach for the user.
    </tool_usage_policy>
    """

    DISCOURAGED = ""

class QualityPromptVars(str, Enum):
    """Prompt variables for quality standards."""
    
    STANDARDS = """
    <quality_standards>
        - Accuracy: Always prioritize correct results. 
        - Completeness: Be sure to address all parts of the request
        - Honesty: NEVER make up or include false information in your responses. If your answer is not accurate or you are not certain, you MUST communicate that in your response.
    </quality_standards>
    """

class ErrorPromptVars(str, Enum):
    """Prompt variables for error handling."""

    HANDLING = """
    <error_handling>
        If you encounter issues:
        1. Acknowledge the problem clearly
        2. Explain what went wrong
        3. Suggest alternative approaches
        4. Ask for clarification if needed
        5. Never guess or provide uncertain information
    </error_handling>
    """

class CommunicationPromptVars(str, Enum):
    """Prompt variables for communication styles."""
    
    PROFESSIONAL = """
    <communication_style>
        - Professional and knowledgeable tone
        - Clear structure with logical flow
        - Appropriate technical detail for the audience
        - Concise but complete responses
    </communication_style>
    """
    
    FRIENDLY = """
    <communication_style>
        - Warm and approachable tone
        - Conversational language
        - Encouraging and supportive
        - Easy to understand explanations
    </communication_style>
    """

# ---------- Helper function for building prompts ----------

def build_system_prompt(
    role_description: str,
    tool_usage_mode: ToolUsageMode,
    communication_style: CommunicationStyle = CommunicationStyle.PROFESSIONAL
) -> str:
    """Assembles a structured system prompt from predefined components."""
    tool_directive_map = {
        ToolUsageMode.MANDATORY: ToolPromptVars.MANDATORY.value,
        ToolUsageMode.PREFERRED: ToolPromptVars.PREFERRED.value,
        ToolUsageMode.OPTIONAL: ToolPromptVars.OPTIONAL.value,
        ToolUsageMode.DISCOURAGED: ToolPromptVars.DISCOURAGED.value,
    }
    comm_style_map = {
        CommunicationStyle.PROFESSIONAL: CommunicationPromptVars.PROFESSIONAL.value,
        CommunicationStyle.FRIENDLY: CommunicationPromptVars.FRIENDLY.value,
    }

    role_definition_var = f"<role_definition>\n    {role_description}\n</role_definition>"
    
    # Use .value to get the string content from the enums
    components = [
        role_definition_var,
        tool_directive_map.get(tool_usage_mode),
        QualityPromptVars.STANDARDS.value,
        comm_style_map.get(communication_style),
        ErrorPromptVars.HANDLING.value,
    ]
    
    return "\n\n".join(c.strip() for c in components if c and c.strip())

