from llama_index.llms.bedrock import Bedrock
from llama_index.core import Settings
from llama_index.core import PropertyGraphIndex

from llama_index.core.indices.property_graph import (
    TextToCypherRetriever
)

from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore

from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.bedrock import BedrockEmbedding
import json
import os

from neo4j import GraphDatabase
from llama_index.core.retrievers import KnowledgeGraphRAGRetriever
from llama_index.core import StorageContext


graph_store = Neo4jPropertyGraphStore(
    username="neo4j",
    password="prahar@156",
    url="bolt://localhost:7687",
    database="neo4j"  # Replace with your database name if different
)

# Initialize Bedrock LLM
# Initialize the Bedrock LLM
llm = Bedrock(
    model="anthropic.claude-3-haiku-20240307-v1:0",  # Specify the desired model
    region_name="us-east-1"          # e.g., "us-east-1"
)
Settings.llm = llm

# # llm = OpenAI(model="gpt-3.5-turbo", temperature=0.3)

embed_model = BedrockEmbedding(
    region_name="us-east-1",  # Replace with your AWS region
    model_name="amazon.titan-embed-text-v2:0"  # Specify the Titan embedding model
)

index = PropertyGraphIndex.from_existing(
    property_graph_store=graph_store,
    llm=llm,
    embed_model=embed_model,
)

# Initialize Neo4j driver
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "prahar@156"

# File path to store the nodes_text
NODES_TEXT_FILE = "nodes_context.txt"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

question = "Who is the owner of Adani Enterprise?"

# Function to fetch all nodes from Neo4j
def fetch_nodes(tx):
    query = """
    MATCH (n)
    RETURN elementId(n) AS id, labels(n) AS labels, n.name AS name
    """
    result = tx.run(query)
    return [{"id": record["id"], "labels": record["labels"], "name": record["name"]} for record in result]

# Function to format nodes for LLM prompt
def format_nodes_for_prompt(nodes):
    formatted_nodes = "\n".join(
        f"Node ID: {node['id']}, Labels: {', '.join(node['labels'])}, Name: {node['name'] or 'N/A'}"
        for node in nodes
    )
    prompt_text = (
        "The following are the nodes in the knowledge graph:\n"
        f"{formatted_nodes}\n"
        "Use this information to identify relevant entities for the user's question."
    )
    return prompt_text

# Function to store nodes_text to a file
def store_nodes_text_to_file(nodes_text, file_path):
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(nodes_text)
    print(f"Context saved to {file_path}")

# Function to load nodes_text from a file
def load_nodes_text_from_file(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            nodes_text = f.read()
        print(f"Context loaded from {file_path}")
        return nodes_text
    else:
        print(f"No existing context found at {file_path}")
        return None

# Function to use LLM for entity identification
def identify_entities_with_llm(question, nodes_text):
    prompt = f"""
    {nodes_text}

    Given the user's question: "{question}"

    Instructions:
    - Identify the most relevant node names or IDs from the graph that match the user's query. 
    - Refine the question and include the exact entity name found in the available information. 
    - After the question, include the Node IDs of the entities involved after the question. 
        For example:
        Question: What are the risks associated with Adani Enterprises?
        Answer: What are the risks associated with Adani Enterprises Limited? 

        Relevant Node IDs: [4:b16o2424-92e8-4379-2895-c43829d35b7a:163, ...]
    - Do not output anything extra than this.
    """
    response = llm.complete(prompt)
    return response

# Main workflow
with driver.session() as session:
    # Step 1: Load nodes_text from file or fetch from Neo4j
    nodes_text = load_nodes_text_from_file(NODES_TEXT_FILE)
    if nodes_text is None:
        # Fetch nodes from Neo4j if not already saved
        nodes = session.execute_read(fetch_nodes)
        nodes_text = format_nodes_for_prompt(nodes)
        store_nodes_text_to_file(nodes_text, NODES_TEXT_FILE)

    # Step 2: Use LLM to identify relevant nodes
    refined_question = identify_entities_with_llm(question, nodes_text)

    print("Refined Question:")
    print(refined_question)

# Define your response and Cypher templates
DEFAULT_RESPONSE_TEMPLATE = (
    "Generated Cypher query:\n{query}\n\n" "Cypher Response:\n{response}"
)
DEFAULT_ALLOWED_FIELDS = ["Company", "Executive", "Risk"]  # Customize based on your schema

DEFAULT_TEXT_TO_CYPHER_TEMPLATE = index.property_graph_store.text_to_cypher_template

# Initialize TextToCypherRetriever
cypher_retriever = TextToCypherRetriever(
    index.property_graph_store,
    llm=llm,  # Use Bedrock LLM initialized earlier
    text_to_cypher_template=DEFAULT_TEXT_TO_CYPHER_TEMPLATE,
    response_template=DEFAULT_RESPONSE_TEMPLATE,
    cypher_validator=None,  # Add custom validation if needed
    allowed_output_field=DEFAULT_ALLOWED_FIELDS,
)

# Retrieve nodes using the TextToCypherRetriever
# response = cypher_retriever.retrieve(str(refined_question))

# Assuming `response` is the result from the retriever
# for node_with_score in response:
#     # Access the TextNode inside NodeWithScore
#     text_node = node_with_score.node
    
#     # Extract the text field
#     text = text_node.text
    
#     # Split the text into query and response sections
#     query_start = text.find("Generated Cypher query:") + len("Generated Cypher query:\n")
#     query_end = text.find("\n\nCypher Response:")
#     query = text[query_start:query_end].strip()
    
#     response_start = query_end + len("\n\nCypher Response:\n")
#     response_content = text[response_start:].strip()
    
#     print("Generated Cypher Query:")
#     print(query)
#     print("\nCypher Response:")
#     print(response_content)

base_retriever = index.as_retriever(sub_retrievers=[cypher_retriever])

#response = base_retriever.retrieve(str(refined_question))

# for node_with_score in response:
#     # Access the TextNode inside NodeWithScore
#     text_node = node_with_score.node
    
#     # Extract the text field
#     text = text_node.text
    
#     # Split the text into query and response sections
#     query_start = text.find("Generated Cypher query:") + len("Generated Cypher query:\n")
#     query_end = text.find("\n\nCypher Response:")
#     query = text[query_start:query_end].strip()
    
#     response_start = query_end + len("\n\nCypher Response:\n")
#     response_content = text[response_start:].strip()
    
#     print("Generated Cypher Query:")
#     print(query)
#     print("\nCypher Response:")
#     print(response_content)

query_engine = RetrieverQueryEngine.from_args(
    retriever=base_retriever, llm=llm
)

response = query_engine.query(str(refined_question))

print(str(response))

storage_context = StorageContext.from_defaults(graph_store=graph_store)

graph_rag_retriever = KnowledgeGraphRAGRetriever(
    storage_context=storage_context,
    verbose=True,
)

query_engine = RetrieverQueryEngine.from_args(
    graph_rag_retriever,
)

response = query_engine.query(str(refined_question))

print(str(response))