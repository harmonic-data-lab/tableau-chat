# Web UI Libraries
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager

# MCP libraries
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# LangChain Libraries
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent, ToolNode
from langchain_core.messages import HumanMessage, trim_messages
from langgraph.checkpoint.memory import InMemorySaver

# Set Local MCP Logging
from utilities.logging_config import setup_logging
logger = setup_logging("dashboard_app.log")

# Load System Prompt and Message Formatter
from utilities.prompt import AGENT_SYSTEM_PROMPT as SUPERSTORE_AGENT_SYSTEM_PROMPT
from utilities.chat import format_agent_response

# Load Environment and set MCP Filepath
import os
import uuid
from dotenv import load_dotenv
load_dotenv()

# Single thread ID for the lifetime of this server process — gives multi-turn
# memory within a session while guaranteeing a clean slate on restart
SESSION_THREAD_ID = str(uuid.uuid4())

### Override existing MCP Location and Toolset to import custom tools from:
# https://github.com/wjsutton/tableau-mcp-experimental for dashboard extension
# Remember to execute 'npm install' & 'npm run build' in the tableau-mcp-experimental folder
# These tools are fixed to 1 datasource via the FIXED_DATASOURCE_LUID environment variable in your .env file
mcp_location = '/Users/austinkness/Tableau MCP/tableau-mcp-experimental/build/index.js'
tool_list = 'list-fields-fixed, query-datasource-fixed'
datasource_luid = os.environ.get('FIXED_DATASOURCE_LUID')

custom_env = {
    **os.environ,
    "INCLUDE_TOOLS": tool_list,
    "FIXED_DATASOURCE_LUID": datasource_luid,
    "MAX_RESULT_LIMIT": "100",  # cap rows returned to keep context small
}

# Set Langfuse Tracing
from langfuse.langchain import CallbackHandler
langfuse_handler = CallbackHandler()

# Global variables for agent and session
agent = None
session_context = None

# Global async context manager for MCP connection
@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    logger.info("Starting up application...")
    
    try:
        # Setup MCP connection
        server_params = StdioServerParameters(
            command="node",
            args=[mcp_location],
            env=custom_env
        )

        # Use proper async context management
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as client_session:
                # Initialize the connection
                await client_session.initialize()

                # Get tools, filter tools using the .env config
                mcp_tools = await load_mcp_tools(client_session)
                
                # Set AI Model — max_retries=0 so rate limit errors fail fast
                # rather than waiting minutes for OpenAI's internal backoff
                llm = ChatOpenAI(model="gpt-4o-mini", temperature=0, max_retries=0)

                # Trim history to last 10 messages before each LLM call so old
                # tool results don't contaminate new queries or bloat the context
                def trim_history(state):
                    return {"messages": trim_messages(
                        state["messages"],
                        max_tokens=10,
                        token_counter=len,
                        strategy="last",
                        include_system=True,
                        allow_partial=False,
                    )}

                checkpointer = InMemorySaver()
                tool_node = ToolNode(mcp_tools, handle_tool_errors=True)
                agent = create_react_agent(model=llm, tools=tool_node, prompt=SUPERSTORE_AGENT_SYSTEM_PROMPT, checkpointer=checkpointer, pre_model_hook=trim_history)
                
                yield
        
    # Error Handling
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise

# Create FastAPI app with lifespan
app = FastAPI(
    title="Tableau AI Chat", 
    description="Simple AI chat interface for Tableau data",
    lifespan=lifespan
)

# Serve static files (HTML, CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Request/Response models
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str



@app.get("/")
def home():
    """Serve the main HTML page"""
    return FileResponse('static/index.html')

@app.get("/index.html")
def static_index():
    return FileResponse('static/index.html')

@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Handle chat messages - this is where the AI magic happens"""
    global agent
    
    if agent is None:
        logger.error("Agent not initialized")
        raise HTTPException(status_code=500, detail="Agent not initialized. Please restart the server.")
    
    try:      
        # Create proper message format for LangGraph
        messages = [HumanMessage(content=request.message)]

        # Get response from agent
        response_text = await format_agent_response(agent, messages, langfuse_handler, SESSION_THREAD_ID)
        
        return ChatResponse(response=response_text)
        
    # Error Handling
    except Exception as e:
        logger.error(f"Error processing chat request: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

# Run the app
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)