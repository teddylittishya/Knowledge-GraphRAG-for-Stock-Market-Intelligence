from llama_index.embeddings.bedrock import BedrockEmbedding
import os

# Initialize the Bedrock Embedding Model
embed_model = BedrockEmbedding(
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name=os.getenv("AWS_REGION"),  # Ensure this environment variable is set
    model_name="amazon.titan-embed-text-v2:0"    # Specify the desired embedding model
)

# Sample text to embed
text = "This is a test document."

# Generate the embedding
embedding = embed_model.get_text_embedding(text)

# Print the embedding vector
print("Embedding vector:", embedding)
