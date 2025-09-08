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

async def send_streaming_message(session, url):
    """Sends a streaming JSON-RPC message to the agent and processes the stream."""
    payload = {
      "jsonrpc": "2.0",
      "id": "12345",
      "method": "message/stream",  # Change method to "message/stream"
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

    print(f"\n🚀 Sending request to {url} with method 'message/stream'...")
    try:
        async with session.post(url, json=payload) as response:
            if response.status == 200:
                print("✅ Received streaming response. Processing chunks...")
                async for chunk in response.content.iter_any():
                    # Process each chunk of the stream as it arrives
                    if chunk:
                        print(f"Chunk received: {chunk.decode('utf-8')}")
            else:
                text_response = await response.text()
                print(f"❌ Error: Received status code {response.status}")
                print(f"Response body: {text_response}")
    except aiohttp.ClientError as e:
        print(f"❌ AIOHTTP ClientError: {e}")

async def main():
    url = "http://localhost:9999/"

    async with aiohttp.ClientSession() as session:
        await fetch_agent_card(session, url)
        await send_streaming_message(session, url)  # Use the new streaming function

if __name__ == "__main__":
    asyncio.run(main())