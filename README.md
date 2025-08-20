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

## MCP 

The _"saop scaffold <agent_name>"_ command will also configure a basic MCP server implementation and a MCP client that lists & calls tools.

_Start by running the MCP server_

```
#cd into the newly created directory
cd legeal_agent

#run the MCP server
python mcp_server.py
```

_Then run the MCP client to list and use tools_

```
#start the the MCP client
python mcp_client.py
```

![Diagram](https://github.com/djtoler/Resume-Refiner-AI-Workflow/blob/main/images/n8n_diagram01.png)


## LangGraph

The _"saop scaffold <agent_name>"_ command will also configure a basic LangGraph tool wrapper implementation that will wrap your MCP tools and execute your tools via LLM calls.

Make sure the MCP server is still running, then run/test the LangGraph tool wrapper

```
python mcp_server.py
```

Your LLM should use your _greet tool_ for the first test prompt and should NOT use any tool for the second test prompt

![Diagram](https://github.com/djtoler/Resume-Refiner-AI-Workflow/blob/main/images/n8n_diagram01.png)