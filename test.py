from google import genai
from google.genai import types

client = genai.Client(api_key="AIzaSyDQ6TEXoUqX963Mop7f71heOG9a---lwPM")

message = input("Enter your question: ")



grounding_tool = types.Tool(
    google_search=types.GoogleSearch()
)

config = types.GenerateContentConfig(
    tools=[grounding_tool]
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=message,
    config=config,
)

print(response.text)