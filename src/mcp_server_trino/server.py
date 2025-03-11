import asyncio
import logging
import os
from mcp.server import Server
from mcp.types import Resource, Tool, TextContent
from pydantic import AnyUrl

# Trino DB-API
# pip install trino
from trino.dbapi import connect
from trino.exceptions import TrinoExternalError, TrinoQueryError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("mcp_server_trino")

def get_db_config():
    """Get Trino configuration from environment variables."""
    config = {
        "host": os.getenv("TRINO_HOST", "localhost"),
        "port": int(os.getenv("TRINO_PORT", "8080")),
        "user": os.getenv("TRINO_USER"),
        "password": os.getenv("TRINO_PASSWORD", ""),  # optional, depends on your Trino setup
        "catalog": os.getenv("TRINO_CATALOG"),
        "schema": os.getenv("TRINO_SCHEMA")
    }

    # Basic validation
    if not all([config["host"], config["port"], config["user"], config["catalog"], config["schema"]]):
        logger.error("Missing required Trino configuration. Please check environment variables:")
        logger.error("TRINO_HOST, TRINO_PORT, TRINO_USER, TRINO_CATALOG, and TRINO_SCHEMA are required")
        raise ValueError("Missing required Trino configuration")

    return config

def create_trino_connection():
    """Create a Trino connection using the environment-based config with Basic Authentication."""
    from trino.auth import BasicAuthentication
    
    cfg = get_db_config()
    
    # Set up Basic Authentication if password is provided
    auth = None
    if cfg["password"]:
        auth = BasicAuthentication(cfg["user"], cfg["password"])
    
    return connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        catalog=cfg["catalog"],
        schema=cfg["schema"],
        http_scheme="https" if cfg["password"] else "http",
        auth=auth
    )

# Initialize server
app = Server("mcp_server_trino")



@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    List available Trino tools (here just a generic SQL executor).
    """
    logger.info("Listing tools...")
    return [
        Tool(
            name="execute_sql",
            description="Execute an SQL query on the Trino cluster",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL query to execute"
                    }
                },
                "required": ["query"]
            }
        )
    ]

# Update these functions to not use cursor as a context manager

@app.list_resources()
async def list_resources() -> list[Resource]:
    """
    List tables in the configured Trino catalog & schema as resources.
    """
    config = get_db_config()
    catalog = config["catalog"]
    schema = config["schema"]

    try:
        conn = create_trino_connection()
        cursor = conn.cursor()
        # Query the schema for tables; "SHOW TABLES IN catalog.schema" is valid in Trino
        show_tables_sql = f"SHOW TABLES IN {catalog}.{schema}"
        cursor.execute(show_tables_sql)
        tables = cursor.fetchall()  # each row is like ('table_name',)
        logger.info(f"Found tables: {tables}")
        
        resources = []
        for (table_name,) in tables:
            resources.append(
                Resource(
                    # e.g. trino://mytable/data
                    uri=f"trino://{table_name}/data",
                    name=f"Table: {table_name}",
                    mimeType="text/plain",
                    description=f"Data in table: {table_name}"
                )
            )
        cursor.close()
        conn.close()
        return resources

    except (TrinoQueryError, TrinoExternalError) as e:
        logger.error(f"Failed to list resources: {str(e)}")
        return []

@app.read_resource()
async def read_resource(uri: AnyUrl) -> str:
    """
    Read up to 100 rows from the given table resource.
    Expects a URI like: trino://table_name/data
    """
    config = get_db_config()
    catalog = config["catalog"]
    schema = config["schema"]
    uri_str = str(uri)
    logger.info(f"Reading resource: {uri_str}")

    if not uri_str.startswith("trino://"):
        raise ValueError(f"Invalid URI scheme: {uri_str}")

    # Grab the table name: "trino://table/data" -> "table"
    parts = uri_str[8:].split('/')
    table = parts[0]

    try:
        conn = create_trino_connection()
        cursor = conn.cursor()
        query = f"SELECT * FROM {catalog}.{schema}.{table} LIMIT 100"
        logger.info(f"Executing query: {query}")
        cursor.execute(query)

        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        result_lines = [",".join(map(str, row)) for row in rows]
        header_line = ",".join(columns)
        
        cursor.close()
        conn.close()
        return "\n".join([header_line] + result_lines)

    except (TrinoQueryError, TrinoExternalError) as e:
        logger.error(f"Database error reading resource {uri_str}: {str(e)}")
        raise RuntimeError(f"Database error: {str(e)}")

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Execute SQL commands on Trino.
    """
    logger.info(f"Calling tool: {name} with arguments: {arguments}")

    if name != "execute_sql":
        raise ValueError(f"Unknown tool: {name}")

    query = arguments.get("query")
    if not query:
        raise ValueError("Query is required")

    try:
        conn = create_trino_connection()
        cursor = conn.cursor()
        logger.info(f"Executing query: {query}")
        cursor.execute(query)

        # For statements like SHOW TABLES, we fetch and return them
        if query.strip().upper().startswith("SHOW "):
            rows = cursor.fetchall()
            # Typically, 'SHOW TABLES IN catalog.schema' returns rows of table names
            result = []
            for row in rows:
                # row could be a tuple like ('table_name',), or more columns depending on "SHOW"
                result.append("\t".join(map(str, row)))
            cursor.close()
            conn.close()
            return [TextContent(type="text", text="\n".join(result))]

        # For SELECT queries, fetch data
        elif query.strip().upper().startswith("SELECT"):
            columns = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            result_lines = [",".join(map(str, row)) for row in rows]
            header_line = ",".join(columns)
            cursor.close()
            conn.close()
            return [TextContent(type="text", text="\n".join([header_line] + result_lines))]

        # For other queries (CREATE, DROP, INSERT, etc.), just return success info
        else:
            # Trino typically doesn't require commit; it's auto-commit style
            cursor.close()
            conn.close()
            return [TextContent(type="text", text="Query executed successfully.")]

    except (TrinoQueryError, TrinoExternalError) as e:
        logger.error(f"Error executing query '{query}': {e}")
        return [TextContent(type="text", text=f"Error executing query: {str(e)}")]

async def main():
    """Main entry point to run the MCP server via STDIO."""
    from mcp.server.stdio import stdio_server

    logger.info("Starting Trino MCP server...")
    config = get_db_config()
    logger.info(f"Trino config: {config['host']}:{config['port']}/{config['catalog']}.{config['schema']} as {config['user']}")

    async with stdio_server() as (read_stream, write_stream):
        try:
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )
        except Exception as e:
            logger.error(f"Server error: {str(e)}", exc_info=True)
            raise

if __name__ == "__main__":
    asyncio.run(main())