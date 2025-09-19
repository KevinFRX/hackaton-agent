import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# This part is just to create a basic agent object
model = LiteLlm(model="gemini-1.5-pro-preview-0514")
agent = Agent(
    name="test_agent",
    model=model,
    description="A test agent.",
    instruction="Just an instruction.",
    tools=[]
)

# This line prints all methods and attributes of the agent object
print(dir(agent))