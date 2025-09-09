#app.py
import asyncio
from telemetry._telemetry import init_tracing 
from agent2agent.a2a_server import main

init_tracing()

if __name__ == "__main__":
    asyncio.run(main())
    