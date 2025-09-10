# langchain/langchain_chains.py (Using system prompts from roles.py)
from typing import Dict
from pydantic import BaseModel
from langchain_core.runnables import Runnable, RunnableLambda
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers.string import StrOutputParser

# Import from your actual files
from config.roles import get_roles
from _mcp.tools import TOOLS

from config.agent_config import load_env_config

env_config = load_env_config()
llm = init_chat_model(
    model=env_config["MODEL_NAME"],
    openai_api_key=env_config["MODEL_API_KEY"],
    model_provider=env_config["MODEL_PROVIDER"]
)

# Get role definitions from roles.py
roles_config = get_roles()

def create_chain_for_role(role_name: str) -> Runnable:
    """Create a chain using the system prompt from roles.py"""
    if role_name not in roles_config:
        raise ValueError(f"Role '{role_name}' not found in roles configuration")
    
    system_prompt = roles_config[role_name]["system_prompt"]
    
    return ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ]) | llm | StrOutputParser()

# Create chains for each role defined in roles.py
chains: Dict[str, Runnable] = {}

# Add chain for each role
for role_name in roles_config.keys():
    print("ROLE NAME: ", role_name)
    chains[role_name] = create_chain_for_role(role_name)



# Add router chain
router_prompt = ChatPromptTemplate.from_template("""
    You are a routing assistant. Route user requests to the appropriate role:

    Available roles and their capabilities:
    - "general_support": Be concise, friendly, and helpful. (Can use: get_weather, healthcheck)
    - "math": Answer calculation questions; prefer numbers over prose. (Can use: add)  
    - "ops_guarded": Ask for confirmation before risky or destructive actions. (Can use: healthcheck)

    Available tools: {available_tools}

    Respond with just the role name: general_support, math, or ops_guarded

    User message: {{input}}
""".format(available_tools=", ".join(TOOLS.keys())))

class Route(BaseModel):
    next_node: str

router_chain = (
    router_prompt
    | llm.with_structured_output(Route)
    | RunnableLambda(lambda x: x.next_node)
)
chains["router"] = router_chain

