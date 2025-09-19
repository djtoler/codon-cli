#!/usr/bin/env python3
"""
Simple SSE Streaming Test Client for SAOP Platform
Non-interactive client that runs automated tests using environment configuration.
"""

import asyncio
import aiohttp
import json
import argparse
from datetime import datetime
from typing import Optional, Dict, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SimpleSSEClient:
    """Simple test client for SAOP SSE streaming API"""
    
    def __init__(self, base_url: str = "http://localhost:9999"):
        self.base_url = base_url.rstrip('/')
        self.token = None
        self.session = None
        
        # Default credentials from your .env
        self.username = "dev"
        self.password = "dev123"
        self.api_key = "dev-api-key-12345"
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    @property
    def headers(self) -> Dict[str, str]:
        """Get authentication headers"""
        headers = {'Content-Type': 'application/json'}
        if self.token:
            headers['Authorization'] = f'Bearer {self.token}'
        return headers
    
    async def authenticate(self) -> bool:
        """Authenticate using JWT"""
        auth_url = f"{self.base_url}/api/v1/auth/token"
        
        data = {
            'username': self.username,
            'password': self.password,
            'grant_type': 'password'
        }
        
        try:
            async with self.session.post(
                auth_url, 
                data=data,
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    self.token = result['access_token']
                    logger.info(f"Authenticated as {self.username}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Authentication failed: {response.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False
    
    async def submit_task(self, message: str, agent_role: str = "general_support") -> Optional[str]:
        """Submit a task and return task ID"""
        submit_url = f"{self.base_url}/api/v1/streaming/tasks/submit"
        
        payload = {
            "message": message,
            "agent_role": agent_role,
            "stream_traces": True,
            "stream_costs": True
        }
        
        logger.info(f"Submitting task: {message}")
        
        try:
            async with self.session.post(submit_url, json=payload, headers=self.headers) as response:
                if response.status == 200:
                    result = await response.json()
                    task_id = result['task_id']
                    logger.info(f"Task submitted: {task_id}")
                    return task_id
                else:
                    error_text = await response.text()
                    logger.error(f"Task submission failed: {response.status} - {error_text}")
                    return None
        except Exception as e:
            logger.error(f"Task submission error: {e}")
            return None
    
    async def stream_task_events(self, task_id: str, timeout: int = 120):
        """Stream task events and log them"""
        stream_url = f"{self.base_url}/api/v1/streaming/tasks/{task_id}/stream"
        
        logger.info(f"Starting stream for task {task_id}")
        
        try:
            async with self.session.get(
                stream_url, 
                headers={**self.headers, 'Accept': 'text/event-stream'},
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Stream failed: {response.status} - {error_text}")
                    return False
                
                logger.info("Connected to event stream")
                
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    
                    if line.startswith('data: '):
                        try:
                            event_data = json.loads(line[6:])
                            self._log_event(event_data)
                            
                            if event_data.get('data', {}).get('final', False):
                                logger.info("Stream completed")
                                return True
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"Failed to parse event: {line}")
                            
        except asyncio.TimeoutError:
            logger.error(f"Stream timeout after {timeout} seconds")
            return False
        except Exception as e:
            logger.error(f"Stream error: {e}")
            return False
    
    def _log_event(self, event_data: Dict[str, Any]):
        """Log SSE event in a clean format"""
        event_type = event_data.get('event', 'unknown')
        data = event_data.get('data', {})
        
        timestamp = datetime.now().strftime('%H:%M:%S')
        
        if event_type == 'connection':
            logger.info(f"[{timestamp}] CONNECTED")
            
        elif event_type == 'progress':
            status = data.get('status', 'unknown')
            message = data.get('message', 'No message')
            logger.info(f"[{timestamp}] PROGRESS: {message}")
            
        elif event_type == 'trace':
            trace_id = data.get('trace_id', 'N/A')[:16]
            duration = data.get('duration_ms', 0)
            logger.info(f"[{timestamp}] TRACE: {trace_id}... ({duration:.1f}ms)")
            
        elif event_type == 'cost':
            total_cost = data.get('total_cost', 0)
            total_tokens = data.get('total_tokens', 0)
            logger.info(f"[{timestamp}] COST: ${total_cost:.4f} ({total_tokens} tokens)")
            
        elif event_type == 'completion':
            result = data.get('result', 'No result')
            print(result, "data: ", data)
            logger.info(f"[{timestamp}] COMPLETED: {result[:100]}...")
            
        elif event_type == 'error':
            error = data.get('error', 'Unknown error')
            logger.error(f"[{timestamp}] ERROR: {error}")
            
        elif event_type == 'keepalive':
            logger.debug(f"[{timestamp}] KEEPALIVE")

async def run_test_scenario(client: SimpleSSEClient, message: str, agent_role: str):
    """Run a single test scenario"""
    logger.info(f"\n{'='*50}")
    logger.info(f"TEST: {message}")
    logger.info(f"AGENT: {agent_role}")
    logger.info(f"{'='*50}")
    
    # Submit task
    task_id = await client.submit_task(message, agent_role)
    if not task_id:
        logger.error("Failed to submit task")
        return False
    
    # Stream events
    success = await client.stream_task_events(task_id)
    
    if success:
        logger.info("Test scenario completed successfully")
    else:
        logger.error("Test scenario failed")
    
    return success

async def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description='Simple SAOP SSE Test Client')
    parser.add_argument('--url', default='http://localhost:9999', help='Base URL')
    parser.add_argument('--quick', action='store_true', help='Run quick test only')
    parser.add_argument('--single', help='Run single test with custom message')
    parser.add_argument('--agent', default='general_support', help='Agent role for single test')
    
    args = parser.parse_args()
    
    # Test scenarios
    if args.single:
        scenarios = [(args.single, args.agent)]
    elif args.quick:
        scenarios = [
            ("What is 2+2?", "math_specialist")
        ]
    else:
        scenarios = [
            ("Calculate 3776629 + 37784", "math_specialist"),
            ("What is the capital of Japan?", "general_support"),
            ("How old is Larry Ellison from Oracle?", "research_assistant"),
            # ("Calculate the sum of all prime numbers between 1 and 10,000. For each prime number found, provide a streaming update to the console, showing the number of primes found so far and the current sum.", "math_specialist")
            ("Are we healthy?", "")
        ]
    
    logger.info("Starting SAOP SSE Test Client")
    logger.info(f"Target URL: {args.url}")
    logger.info(f"Test scenarios: {len(scenarios)}")
    
    async with SimpleSSEClient(args.url) as client:
        # Authenticate
        if not await client.authenticate():
            logger.error("Authentication failed, exiting")
            return
        
        # Run test scenarios
        successful_tests = 0
        
        for i, (message, agent_role) in enumerate(scenarios, 1):
            logger.info(f"\nRunning scenario {i}/{len(scenarios)}")
            
            success = await run_test_scenario(client, message, agent_role)
            if success:
                successful_tests += 1
            
            # Wait between tests
            if i < len(scenarios):
                logger.info("Waiting 2 seconds before next test...")
                await asyncio.sleep(2)
        
        # Summary
        logger.info(f"\n{'='*50}")
        logger.info(f"TEST SUMMARY")
        logger.info(f"Successful: {successful_tests}/{len(scenarios)}")
        logger.info(f"Success rate: {successful_tests/len(scenarios)*100:.1f}%")
        logger.info(f"{'='*50}")

if __name__ == "__main__":
    asyncio.run(main())