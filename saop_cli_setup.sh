#!/bin/bash

set -e

echo "🚀 Setting up the SAOP CLI environment..."

if ! command -v poetry &> /dev/null
then
    echo "Poetry is not installed. Please install it first."
    echo "Documentation: https://python-poetry.org/docs/#installation"
    exit 1
fi

echo "Installing project dependencies..."
poetry install --with dev

VENV_PATH=$(poetry env info --path)

if [ -z "$VENV_PATH" ]; then
    echo "Failed to find the virtual environment path."
    exit 1
fi

ACTIVATE_SCRIPT="$VENV_PATH/bin/activate"

if [ ! -f "$ACTIVATE_SCRIPT" ]; then
    echo "Failed to find the activation script at '$ACTIVATE_SCRIPT'."
    exit 1
fi

echo "✅ Environment configured! Starting a new shell with the environment activated."
echo "You can now run 'saop' commands to create AI agents in minutes."
echo ""
echo "Example: saop scaffold my-new-agent"
echo ""

exec bash --rcfile <(echo "source $ACTIVATE_SCRIPT; exec bash -i")