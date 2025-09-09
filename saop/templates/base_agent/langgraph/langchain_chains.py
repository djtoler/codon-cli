# langchain_chains.py

from typing import Dict
from pydantic import BaseModel
from langchain_core.runnables import Runnable, RunnableLambda
from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers.string import StrOutputParser
from langchain_core.output_parsers import JsonOutputParser

# Import the roles that define your specialized agent's personality and purpose
from config.roles import fallback_role, summary_role, router_role
from config.agent_config import load_env_config
env_config = load_env_config()


llm = init_chat_model(
    model=env_config["MODEL_NAME"],
    openai_api_key=env_config["MODEL_API_KEY"],
    model_provider=env_config["MODEL_PROVIDER"]
)


fallback_chain = ChatPromptTemplate.from_messages([
    ("system", fallback_role),
    ("human", "{input}"),
]) | llm | StrOutputParser()

summary_chain = ChatPromptTemplate.from_messages([
    ("system", summary_role),
    ("human", "{input}"),
]) | llm | StrOutputParser()


class Route(BaseModel):
    next_node: str


router_prompt = ChatPromptTemplate.from_template(router_role)


router_chain = (
    router_prompt
    | llm.with_structured_output(Route)
    | RunnableLambda(lambda x: x.next_node)
)


chains: Dict[str, Runnable] = {
    "fallback_chain": fallback_chain,
    "summary_chain": summary_chain,
    "router_chain": router_chain,
}
