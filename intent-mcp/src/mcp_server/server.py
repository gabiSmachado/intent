import httpx, yaml, sys, os
from fastmcp import FastMCP

PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PARENT_DIR not in sys.path:
    sys.path.append(PARENT_DIR)

from utils.logger import get_logger
logger = get_logger("mcp-server", log_file="mcp_server.log", level=20, console_level=20)

# Create an HTTP client for the target API
client = httpx.AsyncClient(base_url="http://127.0.0.1:9100")

CONFIG_FILE_PATH = '../config.yaml'
OPENAPI_SPEC_FILE = 'NetworkSliceBooking.yaml'

if __name__ == "__main__":    
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
                config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Configuration file not found: {CONFIG_FILE_PATH}")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error parsing configuration file: {exc}")
        sys.exit(1)

    try:
       with open(OPENAPI_SPEC_FILE, 'r') as file:
        openapi_spec= yaml.safe_load(file)
    except FileNotFoundError:
        print(f"API file not found: {OPENAPI_SPEC_FILE}")
        sys.exit(1)
    except yaml.YAMLError as exc:
        print(f"Error parsing API file: {exc}")
        sys.exit(1)
 
    mcp = FastMCP.from_openapi(
        openapi_spec=openapi_spec,
        client=client,
        name="MCP Server"
    )
    
    try:
        logger.info("Starting MCP server...")
        mcp.run(transport="http", host= config.get('host'), port=config.get('port'))
    except KeyboardInterrupt:
        logger.info("Server shutting down...")
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        sys.exit(1)