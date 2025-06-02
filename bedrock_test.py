from llama_index.llms.bedrock import Bedrock

# Initialize the Bedrock LLM
llm = Bedrock(
    model="anthropic.claude-3-haiku-20240307-v1:0",  # Specify the desired model
    region_name="us-east-1"          # e.g., "us-east-1"
)

# Perform a simple completion task
prompt = "Once upon a time"
response = llm.complete(prompt)

# Print the response
print("Prompt:", prompt)
print("Response:", response)
