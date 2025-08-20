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

## 📂 Project Structure

The project follows a standard layout for Python packages, with the core CLI logic located within the `saop` directory.

