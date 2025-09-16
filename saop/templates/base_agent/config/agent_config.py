import os
from typing import TypedDict, Optional, List, Dict, Any, Union
import datetime
from dotenv import load_dotenv

class ToolConfig(TypedDict):
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]

class AgentYAMLConfig(TypedDict):
    id: str
    name: str
    description: str
    version: str
    role: str
    prompt_template: str
    resources: List[str]
    knowledge_base: Optional[str]
    graph: Dict
    created: datetime.datetime
    updated: datetime.datetime
    agents: List[str]
    tools: List[ToolConfig]

class EnvironmentConfig(TypedDict):
    # Agent Config
    AGENT_NAME=str
    AGENT_VERSION=str

    # AI Model Configuration
    MODEL_API_KEY: str
    MODEL_BASE_URL: str
    MODEL_NAME: str
    MODEL_TEMPERATURE: float
    MODEL_PROVIDER: str
    
    # A2A Configuration
    A2A_AGENT_CARD_PATH: str
    A2A_HOST: str
    A2A_PORT: int
    
    # MCP Configuration
    MCP_BASE_URL: str
    MCP_HOST: str
    MCP_PORT: int
    MCP_GITHUB_BASE_URL: str
    SAMPLE01_MCP_TOOL_API_KEY: Optional[str]
    SAMPLE02_MCP_TOOL_API_KEY: Optional[str]
    
    # JWT Authentication Configuration
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int
    JWT_ISSUER: str
    JWT_AUDIENCE: str
    API_KEY_HEADER: str
    USER_STORE_TYPE: str
    
    # Default Users (Development)
    DEFAULT_ADMIN_USERNAME: str
    DEFAULT_ADMIN_PASSWORD_HASH: str
    DEFAULT_ADMIN_EMAIL: str
    DEFAULT_DEV_USERNAME: str
    DEFAULT_DEV_PASSWORD_HASH: str
    DEFAULT_DEV_EMAIL: str
    DEFAULT_DEV_API_KEY: str
    
    # Observability Configuration
    OTEL_EXPORTER_OTLP_ENDPOINT: str
    OTEL_SERVICE_NAME: str
    OTEL_EXPORTER_OTLP_PROTOCOL: str
    OTEL_RESOURCE_ATTRIBUTES: str
    OTEL_TRACES_SAMPLER: str
    
    # Database & Caching
    REDIS_URL: Optional[str]
    DATABASE_URL: Optional[str]
    DB_USER: Optional[str]
    DB_PASSWORD: Optional[str]
    DB_HOST: Optional[str]
    DB_PORT: Optional[int]
    DB_NAME: Optional[str]
    
    # Auth & Secret Management
    AUTH_CLIENT_ID: Optional[str]
    AUTH_CLIENT_SECRET: Optional[str]
    HASHICORP_VAULT_ADDR: Optional[str]
    AWS_SECRETS_MANAGER_ARN: Optional[str]
    GITHUB_PAT: Optional[str]

    # FastAPI Security Configuration
    TOKEN_ENDPOINT: str
    DEFAULT_ADMIN_FULL_NAME: str
    DEFAULT_DEV_FULL_NAME: str

class SAOPAgentConfig(TypedDict):
    agent: AgentYAMLConfig
    environment: EnvironmentConfig

def load_env_config() -> EnvironmentConfig:
    # Ensure .env file is loaded before accessing variables
    load_dotenv()
    return EnvironmentConfig(
        #AI Agent Vars
        AGENT_NAME=os.environ.get("AGENT_NAME", "DefaultSAOPAgent"),
        AGENT_VERSION=os.environ.get("AGENT_VERSION", ""),

        # AI Model Vars
        MODEL_API_KEY=os.environ.get("MODEL_API_KEY", ""),
        MODEL_BASE_URL=os.environ.get("MODEL_BASE_URL", ""),
        MODEL_NAME=os.environ.get("MODEL_NAME", "0.0.0.0"),
        MODEL_TEMPERATURE=float(os.environ.get("MODEL_TEMPERATURE", 0.7)),
        MODEL_PROVIDER=os.environ.get("MODEL_PROVIDER", ""),
        
        # A2A Vars
        A2A_AGENT_CARD_PATH=os.environ.get("A2A_AGENT_CARD_PATH", ""),
        A2A_HOST=os.environ.get("A2A_HOST", ""),
        A2A_PORT=int(os.environ.get("A2A_PORT", 9999)),
        
        # MCP Vars
        MCP_BASE_URL=os.environ.get("MCP_BASE_URL", ""),
        MCP_HOST=os.environ.get("MCP_HOST", "127.0.0.1"),
        MCP_PORT=int(os.environ.get("MCP_PORT", "9000")),
        MCP_GITHUB_BASE_URL=os.environ.get("MCP_GITHUB_BASE_URL", ""),
        SAMPLE01_MCP_TOOL_API_KEY=os.getenv("SAMPLE01_MCP_TOOL_API_KEY"),
        SAMPLE02_MCP_TOOL_API_KEY=os.getenv("SAMPLE02_MCP_TOOL_API_KEY"),
        
        # JWT Auth Vars
        JWT_SECRET_KEY=os.environ.get("JWT_SECRET_KEY", "dev-secret-change-in-production"),
        JWT_ALGORITHM=os.environ.get("JWT_ALGORITHM", "HS256"),
        JWT_EXPIRE_MINUTES=int(os.environ.get("JWT_EXPIRE_MINUTES", "30")),
        JWT_ISSUER=os.environ.get("JWT_ISSUER", "langgraph.agent"),
        JWT_AUDIENCE=os.environ.get("JWT_AUDIENCE", "langgraph.users"),
        API_KEY_HEADER=os.environ.get("API_KEY_HEADER", "X-API-Key"),
        USER_STORE_TYPE=os.environ.get("USER_STORE_TYPE", "memory"),
        
        # Default Users
        DEFAULT_ADMIN_USERNAME=os.environ.get("DEFAULT_ADMIN_USERNAME", "admin"),
        DEFAULT_ADMIN_PASSWORD_HASH=os.environ.get("DEFAULT_ADMIN_PASSWORD_HASH", ""),
        DEFAULT_ADMIN_EMAIL=os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@example.com"),
        DEFAULT_DEV_USERNAME=os.environ.get("DEFAULT_DEV_USERNAME", "dev"),
        DEFAULT_DEV_PASSWORD_HASH=os.environ.get("DEFAULT_DEV_PASSWORD_HASH", ""),
        DEFAULT_DEV_EMAIL=os.environ.get("DEFAULT_DEV_EMAIL", "dev@example.com"),
        DEFAULT_DEV_API_KEY=os.environ.get("DEFAULT_DEV_API_KEY", "dev-api-key-12345"),
        
        # OpenTel Vars
        OTEL_EXPORTER_OTLP_ENDPOINT=os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
        OTEL_SERVICE_NAME=os.environ.get("OTEL_SERVICE_NAME", "langgraph.agent"),
        OTEL_EXPORTER_OTLP_PROTOCOL=os.environ.get("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf"),
        OTEL_RESOURCE_ATTRIBUTES=os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "deployment.environment=local,service.version=0.0.1"),
        OTEL_TRACES_SAMPLER=os.environ.get("OTEL_TRACES_SAMPLER", "parentbased_always_on"),
        
        # DB & Cache Vars
        REDIS_URL=os.getenv("REDIS_URL"),
        DATABASE_URL=os.getenv("DATABASE_URL"),
        DB_USER=os.getenv("DB_USER"),
        DB_PASSWORD=os.getenv("DB_PASSWORD"),
        DB_HOST=os.getenv("DB_HOST"),
        DB_PORT=int(os.getenv("DB_PORT", "5432")) if os.getenv("DB_PORT") else None,
        DB_NAME=os.getenv("DB_NAME"),
        
        # Auth Vars
        AUTH_CLIENT_ID=os.getenv("AUTH_CLIENT_ID"),
        AUTH_CLIENT_SECRET=os.getenv("AUTH_CLIENT_SECRET"),
        HASHICORP_VAULT_ADDR=os.getenv("HASHICORP_VAULT_ADDR"),
        AWS_SECRETS_MANAGER_ARN=os.getenv("AWS_SECRETS_MANAGER_ARN"),
        GITHUB_PAT=os.getenv("GITHUB_PAT", ""),

        # FastAPI Security Vars
        TOKEN_ENDPOINT=os.environ.get("TOKEN_ENDPOINT", "auth/token"),
        DEFAULT_ADMIN_FULL_NAME=os.environ.get("DEFAULT_ADMIN_FULL_NAME", "Administrator"),
        DEFAULT_DEV_FULL_NAME=os.environ.get("DEFAULT_DEV_FULL_NAME", "Developer"),

        TEMPLATES_DIR=os.environ.get("TEMPLATES_DIR", "frontend/templates")
    )

if __name__ == "__main__":
    env_config = load_env_config()
    # You can now use the structured object
    print("Loaded Environment Configuration:")
    print(f"Model Name: {env_config['MODEL_NAME']}")
    print(f"MCP Base URL: {env_config['MCP_BASE_URL']}")
    print(f"A2A Port: {env_config['A2A_PORT']}")
    print(f"JWT Issuer: {env_config['JWT_ISSUER']}")
    print(f"Default Admin User: {env_config['DEFAULT_ADMIN_USERNAME']}")
    print(f"Database URL (Optional): {env_config.get('DATABASE_URL')}")