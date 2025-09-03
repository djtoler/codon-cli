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

This command will create a new directory named `legal-agent` with a pre-configured agent template.

#### _Be sure to add GitHub token and LLM config info to .env file_

## MCP 

The _"saop scaffold <agent_name>"_ command will also configure a basic MCP server implementation and a MCP client that lists & calls tools.

_Start by running the MCP server_

```
#cd into the newly created directory
cd legeal_agent

#run the MCP server
python mcp_server.py
```

![Diagram](https://github.com/djtoler/Resume-Refiner-AI-Workflow/blob/main/images/003.png)

_Then run the MCP client to list and use tools_

```
#start the the MCP client
python mcp_client.py
```

![Diagram](https://github.com/djtoler/Resume-Refiner-AI-Workflow/blob/main/images/001.png)


## LangGraph MCP Tool Wrapper

The _"saop scaffold <agent_name>"_ command will also configure a basic LangGraph tool wrapper implementation that will wrap your MCP tools and execute your tools via LLM calls.

Make sure the MCP server is still running, then run/test the LangGraph tool wrapper

```
python mcp_server.py
python langgraph_tool_wrapper.py
```

Your LLM should use your _greet tool_ for the first test prompt and should NOT use any tool for the second test prompt

![Diagram](https://github.com/djtoler/Resume-Refiner-AI-Workflow/blob/main/images/002.png)


## A2A

The _"saop scaffold <agent_name>"_ command will also configure a basic A2A server.

1. Create your A2A AgentCard using the a2a_agent_card.yaml
2. Then run the following command to start your A2A server.

```
python a2a_server.py
```

## Agent Architecture 

![Diagram](https://github.com/djtoler2/imgs/blob/main/SystemArchitecture.png)

| **System Flow** | **Dummy File Names** |
| :--- | :--- |
| 1. An A2A compliant client sends a request to our A2A compliant server. | `a2a_client.py` or `a2a_client_streaming.py` |
| Our A2A server forwards the request to our LangGraph agent. | `a2a_server.py` |
| Our LangGraph agent starts to process the request. | `langgraph_executor.py` |
| If our LangGraph agent decides to use any MCP tools from the tool list, it'll use a tool. The response from the tool will be used in our LangGraph agents response. If our LangGraph agent decides _NOT_ to use any tools from the MCP tool list, it'll respond solely using the LLM its configured with. | `langgraph_tool_wrapper.py` <br> `langgraph_executor.py` |
| Our LangGraph agents response will be formatted into an A2A compliant response, processed by our A2A server, then sent back to the A2A client that initiated the request. | `langgraph_executor.py` <br> `a2a_server.py` <br> `a2a_client.py` or `a2a_client_streaming.py` |

