# SAOP CLI

A command-line tool for scaffolding SAOP (Software Agent Orchestration Platform) agents from a template.

## ✨ Features
- **Quick Scaffolding:** Generate a new agent directory with a single command.
- **Template-Based:** Customize the agent template to suit your needs.
- **Easy Setup:** A simple `saop_cli_setup.sh` script gets you up and running instantly.

## 🚀 Getting Started

Follow these steps to set up and run the `saop` CLI on your local machine.

### Prerequisites

Before you begin, ensure you have the following installed:
- **Python 3.10+:** The project's required Python version.
- **Poetry:** The dependency management tool for this project. If you don't have it, install it with:

```
pip install poetry
```



## Step 1: Clone the Repository

Open your terminal and clone the project from GitHub:

```
git clone https://github.com/djtoler/codon-cli.git
cd saop-cli
```

## Step 2: Install and Configure the Environment

Run the provided install.sh script to automatically set up the virtual environment and install all dependencies:

```
chmod +x ./saop_cli_setup.sh
./saop_cli_setup.sh
```

> **Note:** This script will start a new shell session. Your terminal prompt will change to indicate that the virtual environment is now active.

## Step 3: Run the CLI

You are now ready to scaffold a new agent. You can run the `saop` command directly without any prefixes:

```
saop scaffold <agent_name>
```

**Example:**

```
saop scaffold legal-agent
```

This command will create a new directory named `legal-agent` with a pre-configured agent templates.

## CONFIG

The _"saop scaffold <agent_name>"_ command will create templates for you to build your agent from

_Add your agents enviornment variables in a .env file & to the agent.config.py file_
_Add your customized agent Role configurations in the roles.py file or proceed with default roles_
_Add your customized agent Prompt variables in the vars.py file or proceed with default prompts_


## MCP 

The _"saop scaffold <agent_name>"_ command will also configure a basic MCP server implementation registers local tools.

_Start by running the MCP server_

```
#cd into the base_agent directory of the newly created agent dir
cd legal_agent/templates/base_agent

#run the MCP server
python3 -m _mcp.mcp_server
```

<!-- ![Diagram](https://github.com/djtoler/Resume-Refiner-AI-Workflow/blob/main/images/003.png) -->

<!-- _Then run the MCP client to list and use tools_

```
#start the the MCP client
python mcp_client.py
```

![Diagram](https://github.com/djtoler/Resume-Refiner-AI-Workflow/blob/main/images/001.png) -->
<!-- 

## LangGraph Agent

The _"saop scaffold <agent_name>"_ command will also configure a basic LangGraph agent.

```
python mcp_server.py
python langgraph_agent.py
```

Your LLM should use your _greet tool_ for the first test prompt and should NOT use any tool for the second test prompt

![Diagram](https://github.com/djtoler/Resume-Refiner-AI-Workflow/blob/main/images/002.png) -->


## A2A

The _"saop scaffold <agent_name>"_ command will also configure a basic A2A server using FastAPI as a security layer, OpenTelemetry as a data tracing layer and initialize the execution of our agent using LangGraph.

Run the following command to start your A2A server.

```
python3 app.py
```

## Agent Architecture 

![Diagram](https://github.com/djtoler2/imgs/blob/main/SystemArchitecture.png)

| **System Flow** | **File Names** |
| :--- | :--- |
| 1. An A2A compliant client sends a request to our A2A compliant server. | `tests/test_client.py` |
| 2. Our FastAPI implementation secures our agents by authenticating requests to our A2A server. | `api/auth.py` <br> `api/middleware.py` <br> `api/routes.py` <br> `api/wrapper.py`|
| 3. Our OpenTelemetry implementation provieds trace data for our A2A server | `telemetry/telemetry.py` |
| 4. Our A2A server passes authenticated requests to our LangGraph executor | `langgraph/langgraph_executor.py` |
| 5. Our LangGraph executor uses its role and decision making logic to respond to requests via the _AgentFactory_ configuration| `langgraph/langgraph_agent.py` <br> `langgraph/langchain_chains.py` <br> `langgraph/agent_factory.py`|
| 6. Our agent decides whether to use tools or not, then returns an A2A compliant response | `langgraph/langgraph_agent.py` <br> `langgraph/langgraph_executor.py` <br> `agent2agent/a2a_server.py` |

