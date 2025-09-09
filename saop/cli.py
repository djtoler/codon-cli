import argparse
import os
import shutil
import datetime
from typing import Dict, Any

def scaffold_agent(agent_name: str):
    """
    Scaffolds a new agent directory from a template.
    
    This function now simply copies the entire template directory,
    ensuring all necessary files like graph.py are included.
    """
    # The template directory is relative to the location of this script.
    template_dir = os.path.join(os.path.dirname(__file__), "templates/base_agent")
    new_agent_dir = os.path.join(os.getcwd(), agent_name)

    if not os.path.exists(template_dir):
        print(f"Error: Template directory '{template_dir}' not found.")
        print("Please ensure you have a 'templates/base_agent' directory with your template files.")
        return

    if os.path.exists(new_agent_dir):
        print(f"Error: Directory '{new_agent_dir}' already exists.")
        return

    # Use shutil.copytree to copy the entire template directory recursively.
    shutil.copytree(template_dir, new_agent_dir)
    print(f"Created new agent directory '{new_agent_dir}' from template.")

    print("\n✅ New agent scaffolded successfully!")
    print(f"To get started, navigate to the directory: cd {agent_name}")
    print("Please fill in the placeholder values in your new '.env' and YAML files.")

def main():
    parser = argparse.ArgumentParser(description="SAOP CLI for agent orchestration.")
    subparsers = parser.add_subparsers(dest="command")

    scaffold_parser = subparsers.add_parser("scaffold", help="Create a new agent from a template.")
    scaffold_parser.add_argument("agent_name", type=str, help="The name of the new agent.")

    args = parser.parse_args()

    if args.command == "scaffold":
        scaffold_agent(args.agent_name)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()