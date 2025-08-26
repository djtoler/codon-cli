import asyncio
import aiohttp
import json

async def fetch_agent_card(session, url):
    """Fetches and prints the agent card."""
    agent_card_url = f"{url}.well-known/agent.json"
    print(f"📄 Fetching agent card from {agent_card_url}...")
    try:
        async with session.get(agent_card_url) as response:
            if response.status == 200:
                agent_card = await response.json()
                print("✅ Agent card received successfully:")
                print(json.dumps(agent_card, indent=2))
            else:
                print(f"❌ Failed to fetch agent card. Status: {response.status}")
                print(f"Response body: {await response.text()}")
    except aiohttp.ClientError as e:
        print(f"❌ AIOHTTP ClientError: {e}")

async def send_message(session, url):
    """Sends the JSON-RPC message to the agent."""
    payload = {
      "jsonrpc": "2.0",
      "id": "12345",
      "method": "message/send",
      "params": {
        "message": {
          "messageId": "msg-001",
          "role": "user",
          "parts": [
            {
              "text": "Use the tools available in order to help you name a couple of the toolsets available in the remote-server.md file at the github/github-mcp-server/docs repository?."
            }
          ]
        }
      }
    }

    print(f"\n🚀 Sending request to {url} with method 'message/send'...")
    try:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                json_response = await response.json()
                print("✅ Received response:")
                print(json.dumps(json_response, indent=2))
            else:
                text_response = await response.text()
                print(f"❌ Error: Received status code {response.status}")
                print(f"Response body: {text_response}")
    except aiohttp.ClientError as e:
        print(f"❌ AIOHTTP ClientError: {e}")

async def main():
    # The correct URL for the JSON-RPC endpoint
    url = "http://localhost:9999/"

    async with aiohttp.ClientSession() as session:
        # Step 1: Fetch and print the agent card
        await fetch_agent_card(session, url)

        # Step 2: Send the message
        await send_message(session, url)

if __name__ == "__main__":
    asyncio.run(main())