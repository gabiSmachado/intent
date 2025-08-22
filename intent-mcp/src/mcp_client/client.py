import sys, os, asyncio, json, yaml
from typing import Optional
from contextlib import AsyncExitStack
from dotenv import load_dotenv
from openai import OpenAI
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from utils.logger import get_logger

logger = get_logger("mcp-client", log_file="mcp_client.log", level=20, console_level=20)

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY", "")
if not api_key:
    logger.warning("OPENAI_API_KEY não definida. Defina antes de chamar o LLM.")

CONFIG_FILE_PATH = 'config/config.yaml'

DEFAULT_SERVER_PATH = '/mcp'  # default HTTP path used by FastMCP HTTP transport

class MCPClient:
    def __init__(self, api_key: str):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.llm = OpenAI(api_key=api_key)
        self.tools = []
        self.messages = []
        self.logger = logger
        
    async def connect_to_server(self, host: str, port: int, path: str = DEFAULT_SERVER_PATH):
        """Connect to an MCP server.

        host/port/path are passed explicitly (taken from config in main) so we don't
        silently use a hard‑coded 127.0.0.1 which breaks in Kubernetes.
        """
        # Normalize path
        if path and not path.startswith('/'):
            path = '/' + path
        server_url = f"http://{host}:{port}{path}"
        self.logger.info(f"Attempting to connect to server at {server_url}.")
        try:
            result = await self.exit_stack.enter_async_context(
                streamablehttp_client(server_url)
            )
            if isinstance(result, (tuple, list)):
                if len(result) < 2:
                    raise RuntimeError("streamablehttp_client returned fewer than 2 elements; cannot get read/write streams")
                self.read_stream, self.write_stream = result[0], result[1]
            else:
                self.read_stream = getattr(result, "read_stream", getattr(result, "read", None))
                self.write_stream = getattr(result, "write_stream", getattr(result, "write", None))
                if self.read_stream is None or self.write_stream is None:
                    raise RuntimeError("Unable to locate read/write streams on streamablehttp_client result")

            self.session = await self.exit_stack.enter_async_context(
                ClientSession(self.read_stream, self.write_stream)
            )

            try:
                await self.session.initialize()
            except asyncio.CancelledError as ce:
                # Provide clearer context for the common cancellation symptom the user saw
                raise RuntimeError(
                    "Initialization cancelled. This often means the server URL/path is incorrect or the server did not respond to the MCP initialize request."
                ) from ce

            mcp_tools = await self.get_mcp_tools()
            self.tools = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.inputSchema,
                }
                for tool in mcp_tools
            ]

            self.logger.info(
                f"Successfully connected to server. Available tools: {[tool['name'] for tool in self.tools]}"
            )
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to server at {server_url}: {e}")
            raise


    async def get_mcp_tools(self):
        try:
            self.logger.info("Requesting MCP tools from the server.")
            response = await self.session.list_tools()
            return response.tools
        except Exception as e:
            self.logger.error(f"Failed to get MCP tools: {str(e)}")
            raise Exception(f"Failed to get tools: {str(e)}")


    async def process_intent(self, intent: str):
        """Process an intent: try LLM function call; fallback to heuristic tool call.

        Returns tool result or LLM text message.
        """
        try:
            self.logger.info(f"Processing intent: {intent}")
            user_intent = {"role": "user", "content": intent}
            self.messages = [user_intent]

            self.logger.debug("Calling OpenAI API")
            while True:
                response = self.llm.responses.create(
                    model="gpt-4o-mini",
                    input=json.dumps(self.messages),
                    tools=self.tools,
                )
                message = response.output[0]
    
                if message.type == "message" and len(message.content) == 1:
                    assistant_message = {
                        "role": "assistant",
                        "content": message.content[0].text,
                    }
                    self.messages.append(assistant_message)
                    break
                                
                if message.type == "function_call":
                    assistant_message = assistant_message = {
                        "role": "assistant",
                        "content": message.to_dict()
                    }
                    self.messages.append(assistant_message)
                    
                return json.loads(message.arguments)
        except Exception as e:
            self.logger.error(f"Error processing intent: {e}")
            raise
          
    async def cleanup(self):
        """Clean up resources (close streams & session)."""
        try:
            logger.info("Shuting down MCP connection.")
            await self.exit_stack.aclose()
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
        
                
async def main():
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
                config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Configuration file not found: {CONFIG_FILE_PATH}")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error parsing configuration file: {exc}")
        sys.exit(1)

    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Set OPENAI_API_KEY in your environment or .env")
        sys.exit(1)
        
    client_cfg = config.get('mcp_server', {}) if isinstance(config, dict) else {}
    host = client_cfg.get('host', '127.0.0.1')
    port = int(client_cfg.get('port', 8000))
    path = client_cfg.get('path', DEFAULT_SERVER_PATH)

    client = MCPClient(api_key)
    try:
        await client.connect_to_server(host=host, port=port, path=path)
        response = await client.process_intent("My slice use case is eMBB for an Airport lounge 4-K pipe, and it is crucial to maximize throughput. Push for the highest throughput, to maximize QoS/QoE of our users, with min 60 Mbps and min 10 ms.")
        print(response)
    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(main())