import os
import litellm
from google.adk.agents import Agent, LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools.mcp_tool import McpToolset, SseConnectionParams
from google.adk.tools import agent_tool
from config import AZ_MODEL

litellm.drop_params = True
print('USING ', AZ_MODEL)
MODEL = LiteLlm(model=AZ_MODEL)

# # TESTING ONLY
# root_agent = Agent(
#     model=MODEL,
#     name='root_agent',
#     description='Academic Expert Identification Agent (MCP-backed).',
#     instruction="""
#     You are an academic research assistant"""
# )

# Expansion agent
expansion_agent = LlmAgent(
    model=MODEL,
    name='expansion_agent',
    instruction="""Analyze the user's question and output a search string that can be used in a DUCKDB FTS query like:

    fts_main_documents.match_bm25(d.id, 'query_string')  

    The goal is to maximize recall in an academic DUCKDB FTS search system.

    Include
        * core concepts
        * synonyms
        * related terminology
        * historical or disciplinary variants
        * abbreviations and expanded forms
        
    
    Prefer concise noun phrases over full sentences.
    Avoid overlap between phrases. 
    Avoid stopword-heavy phrases.
    Be consise, do not generate unnecessary phrases. 
    Do not explain your reasoning.

    GENERATE MAXIMUM 50 PHRASES.
    

"""
)

# Setup MCP Tools
mcp_toolset = McpToolset(
    connection_params=SseConnectionParams(
        url=os.getenv("MCP_URL", "http://localhost:9000/sse")
    )
)



# Root Agent
root_agent = Agent(
    model=MODEL,
    name='root_agent',
    description='Academic Expert Identification Agent (MCP-backed).',
    instruction="""
    You are an academic research assistant. You have access to a dump from the Erasmus University CRIS system. 
    1. For EXPERTS: Call expansion_agent, always verify faculty names using get_faculties() before filtering, then get_author_stats, display the top results (up to 10 max.) and the used keywords and suggest to the user to that you can generate a (short) profile for the authors (see 3. For PERSONS and AUTHORS: Call search_authors).
    2. For TOPICS and CONCEPTS and METHODS: Call expansion_agent, always verify faculty names using get_faculties() before filtering, then search_database.
    3. For PERSONS and AUTHORS: Call search_authors, always verify faculty names using get_faculties() before filtering, use the results to create a profile.
    4. For SIMILARY questions: Call most_similar.
    5. For OPEN ENDED questions about the underlying dataset: FIRST call get_schema to inspect the tables, SECOND use summarize_table(table_name) inspect the table. FINALLY use execute_query with the final query that answers the users question.
    """,
    tools=[
        agent_tool.AgentTool(expansion_agent),
        mcp_toolset
    ]
)