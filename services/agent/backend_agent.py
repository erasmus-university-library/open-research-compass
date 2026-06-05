import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ag_ui_adk import ADKAgent, add_adk_fastapi_endpoint
from agent import *

app = FastAPI()

# Add CORS to be safe
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the ADK Agent
agent_middleware = ADKAgent(
    adk_agent=root_agent,
    app_name="duck_agent",
)

# Mount the endpoint at the root "/" for testing
# This usually maps /info directly to the root
add_adk_fastapi_endpoint(app, agent_middleware, path="/")
# if not os.getenv("GOOGLE_API_KEY"):
#     print('wtf!! no key loaded from .env??')
    

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)