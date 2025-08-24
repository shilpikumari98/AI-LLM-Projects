import sys
import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import json
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from doctor_ai_agent import handle_user_query

# No need for custom decimal_default anymore

doctor_server = None

class DoctorServer:
    def __init__(self):
        pass

    async def initialize_pool(self):
        # If you use async DB, initialize here
        pass

    async def close_pool(self):
        # If you use async DB, close here
        pass

    def setup_handlers(self):
        self.tools = {
            "ask_agent": self.ask_agent_handler
        }

    async def call_tool_handler(self, name, arguments):
        handler = self.tools.get(name)
        if not handler:
            raise Exception(f"Tool '{name}' not found")
        return [await handler(**arguments)]

    async def list_tools_handler(self):
        return [ToolInfo(name=k) for k in self.tools.keys()]

    async def ask_agent_handler(self, question: str):
        result = handle_user_query(question)
        return result

class ToolInfo(BaseModel):
    name: str

@asynccontextmanager
async def lifespan(app: FastAPI):
    global doctor_server
    doctor_server = DoctorServer()
    await doctor_server.initialize_pool()
    doctor_server.setup_handlers()
    yield
    if doctor_server:
        await doctor_server.close_pool()

app = FastAPI(title="Doctor Appointments Agent HTTP Server", lifespan=lifespan)

# Add CORS middleware for frontend-backend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your frontend URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static frontend files at /static
frontend_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../frontend'))
app.mount("/static", StaticFiles(directory=frontend_path), name="static")

# Serve index.html at root
@app.get("/")
async def serve_index():
    return FileResponse(os.path.join(frontend_path, "index.html"))

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

class CallToolRequestModel(BaseModel):
    name: str
    arguments: dict

@app.post("/call_tool")
async def call_tool(request: CallToolRequestModel):
    global doctor_server
    handler = getattr(doctor_server, 'call_tool_handler', None)
    if handler is None:
        return JSONResponse(status_code=500, content={"error": "Tool handler not initialized"})
    try:
        result = await handler(request.name, request.arguments)
        text = result[0] if isinstance(result[0], str) else json.dumps(result[0], default=str)
        try:
            data = json.loads(text)
        except Exception:
            data = text
        return JSONResponse(content=data)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/list_tools")
async def list_tools():
    global doctor_server
    handler = getattr(doctor_server, 'list_tools_handler', None)
    if handler is None:
        return JSONResponse(status_code=500, content={"error": "List tools handler not initialized"})
    result = await handler()
    tools = [tool.dict() for tool in result]
    return JSONResponse(content={"tools": tools})
