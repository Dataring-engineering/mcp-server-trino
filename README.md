# Trino MCP Server

This repository provides an MCP (Model-Control-Protocol) server that allows you to list and query tables via Trino using Python.

## Overview

- MCP: MCP is a protocol for bridging AI models, data, and tools. This example MCP server provides:
    - A list of Trino tables as MCP resources
    - Ability to read table contents through MCP
    - A tool for executing arbitrary SQL queries against Trino
- Trino: A fast, distributed SQL query engine for big data analytics. This server makes use of Trino’s Python client (trino.dbapi) to connect to a Trino host, catalog, and schema.

## Requirements

- Python 3.9+ (or a version compatible with mcp, trino, and asyncio)
- trino (the Python driver for Trino)
- mcp (the Model-Control-Protocol Python library)

## Configuration

The server reads Trino connection details from environment variables:

| Variable         | Description                                                          | Default     |
|------------------|----------------------------------------------------------------------|------------|
| `TRINO_HOST`     | Trino server hostname or IP                                          | `localhost`|
| `TRINO_PORT`     | Trino server port                                                    | `8080`     |
| `TRINO_USER`     | Trino user name                                                      | *required* |
| `TRINO_PASSWORD` | Trino password (optional, depends on your authentication setup)      | (empty)    |
| `TRINO_CATALOG`  | Default catalog to use (e.g., `hive`, `tpch`, `postgresql`, etc.)    | *required* |
| `TRINO_SCHEMA`   | Default schema to use (e.g., `default`, `public`, etc.)             | *required* |

## Usage

``` json
{
  "mcpServers": {
    "trino": {
      "command": "uv",
      "args": [
        "--directory", 
        "<path_to_mcp_server_trino>",
        "run",
        "mcp_server_trino"
      ],
      "env": {
        "TRINO_HOST": "<host>",
        "TRINO_PORT": "<port>",
        "TRINO_USER": "<user>",
        "TRINO_PASSWORD": "<password>",
        "TRINO_CATALOG": "<catalog>",
        "TRINO_SCHEMA": "<schema>"
      }
    }
  }
}

```