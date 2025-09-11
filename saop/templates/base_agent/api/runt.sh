#!/bin/bash
# test_sse.sh - Simple test runner for SAOP SSE streaming

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}SAOP SSE Streaming Test Runner${NC}"
echo "=================================="

# Check if Python client exists
if [ ! -f "test.py" ]; then
    echo -e "${RED}Error: test.py not found${NC}"
    echo "Please save the Python client code as 'simple_sse_client.py'"
    exit 1
fi

# Install dependencies if needed
echo -e "${YELLOW}Checking dependencies...${NC}"
python -c "import aiohttp" 2>/dev/null || {
    echo -e "${YELLOW}Installing aiohttp...${NC}"
    pip install aiohttp
}

# Default values from your .env
BASE_URL="http://localhost:9999"

echo -e "${BLUE}Using configuration:${NC}"
echo "  Base URL: $BASE_URL"
echo "  Username: dev"
echo "  API Key: dev-api-key-12345"
echo ""

# Test options
case "${1:-full}" in
    "quick")
        echo -e "${GREEN}Running quick test...${NC}"
        python simple_sse_client.py --url "$BASE_URL" --quick
        ;;
    "single")
        if [ -z "$2" ]; then
            echo -e "${RED}Error: Please provide a message for single test${NC}"
            echo "Usage: $0 single \"Your message here\" [agent_role]"
            exit 1
        fi
        MESSAGE="$2"
        AGENT="${3:-general_support}"
        echo -e "${GREEN}Running single test...${NC}"
        echo "Message: $MESSAGE"
        echo "Agent: $AGENT"
        python simple_sse_client.py --url "$BASE_URL" --single "$MESSAGE" --agent "$AGENT"
        ;;
    "full")
        echo -e "${GREEN}Running full test suite...${NC}"
        python test.py --url "$BASE_URL"
        ;;
    "help")
        echo "Usage: $0 [option]"
        echo ""
        echo "Options:"
        echo "  quick               Run single quick test"
        echo "  single \"message\"    Run single custom test"
        echo "  full                Run full test suite (default)"
        echo "  help                Show this help"
        echo ""
        echo "Examples:"
        echo "  $0                                    # Full test suite"
        echo "  $0 quick                              # Quick test"
        echo "  $0 single \"What is AI?\"               # Custom test"
        echo "  $0 single \"Calculate 5!\" math_specialist  # Custom test with specific agent"
        ;;
    *)
        echo -e "${RED}Unknown option: $1${NC}"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac