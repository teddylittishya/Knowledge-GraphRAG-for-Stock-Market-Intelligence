import os
from llama_index.llms.bedrock import Bedrock
from llama_index.core import Settings
from llama_index.core import PropertyGraphIndex
from llama_index.core.indices.property_graph import TextToCypherRetriever
from llama_index.graph_stores.neo4j import Neo4jPropertyGraphStore
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.embeddings.bedrock import BedrockEmbedding
from neo4j import GraphDatabase
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


# Database configuration
DB_CONFIG = {
    "uri": "bolt://localhost:7687",
    "username": "neo4j",
    "password": "prahar@156"
}

# Initialize Neo4j driver
driver = GraphDatabase.driver(DB_CONFIG["uri"], auth=(DB_CONFIG["username"], DB_CONFIG["password"]))

# Neo4j property graph store
graph_store = Neo4jPropertyGraphStore(
    username=DB_CONFIG["username"],
    password=DB_CONFIG["password"],
    url=DB_CONFIG["uri"],
    database="neo4j"  # Replace with your database name if different
)

# Initialize Bedrock LLM
llm = Bedrock(
    model="anthropic.claude-3-haiku-20240307-v1:0",
    region_name="us-east-1",
    temperature=0.3,                                # Set the desired temperature
    max_tokens=2048
)
Settings.llm = llm

# Initialize Bedrock embedding model
embed_model = BedrockEmbedding(
    region_name="us-east-1",
    model_name="amazon.titan-embed-text-v2:0"
)

# Initialize property graph index
index = PropertyGraphIndex.from_existing(
    property_graph_store=graph_store,
    llm=llm,
    embed_model=embed_model
)

# Initialize TextToCypherRetriever
DEFAULT_RESPONSE_TEMPLATE = (
    "Generated Cypher query:\n{query}\n\n" "Cypher Response:\n{response}\n\n"
)
DEFAULT_ALLOWED_FIELDS = ["Company", "Executive", "Risk", "HAS_RISK", "MANAGED_BY"]
DEFAULT_TEXT_TO_CYPHER_TEMPLATE = index.property_graph_store.text_to_cypher_template

print(DEFAULT_TEXT_TO_CYPHER_TEMPLATE)

cypher_retriever = TextToCypherRetriever(
    index.property_graph_store,
    llm=llm,
    text_to_cypher_template=DEFAULT_TEXT_TO_CYPHER_TEMPLATE,
    response_template=DEFAULT_RESPONSE_TEMPLATE,
    cypher_validator=None,
    allowed_output_field=DEFAULT_ALLOWED_FIELDS,
    verbose=True
)

# Initialize query engine
base_retriever = index.as_retriever(sub_retrievers=[cypher_retriever], )
query_engine = RetrieverQueryEngine.from_args(retriever=base_retriever, llm=llm, verbose=True)

# File path to store nodes context
NODES_TEXT_FILE = "nodes_context.txt"

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

# Function to store nodes context in a file
def store_nodes_text_to_file(nodes_text, file_path):
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(nodes_text)
    print(f"Context saved to {file_path}")

# Function to load nodes context from a file
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
    You are an expert in identifying entities in a knowledge graph. Your role is to understand the user's question and generate an accurate and refined question based on the Graph nodes information I am providing you.

    <Graph Node Information>
    {nodes_text}
    </Graph Node Information>
    
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
    - The refined question should not change the meaning of the question.
    - The user questions can be very broad or very specific, you should identify what the user is try to ask.
    - You shoukd not try to answer the question based on the information you have, A cypher query will be generated based on the refined question. So, do not add additional information to the original question.
    """
    response = llm.complete(prompt)
    return response

# CLI Loop
def main():
    with driver.session() as session:
        # Step 1: Load or generate nodes context
        nodes_text = load_nodes_text_from_file(NODES_TEXT_FILE)
        if nodes_text is None:
            nodes = session.execute_read(fetch_nodes)
            nodes_text = format_nodes_for_prompt(nodes)
            store_nodes_text_to_file(nodes_text, NODES_TEXT_FILE)

        # Step 2: Start CLI
        while True:
            print("\n=== Knowledge Graph RAG ===")
            print("Type your question or 'exit' to quit:")
            question = input(">> ").strip()
            if question.lower() == "exit":
                print("Exiting CLI. Goodbye!")
                break

            # Step 3: Identify relevant entities and refine the question
            refined_question = identify_entities_with_llm(question, nodes_text)
            print("\nRefined Question:")
            print(refined_question)

            response = base_retriever.retrieve(str(refined_question))

            for node_with_score in response:
                # Access the TextNode inside NodeWithScore
                text_node = node_with_score.node
                
                # Extract the text field
                text = text_node.text
                
                # Split the text into query and response sections
                query_start = text.find("Generated Cypher query:") + len("Generated Cypher query:\n")
                query_end = text.find("\n\nCypher Response:")
                query = text[query_start:query_end].strip()
                
                response_start = query_end + len("\n\nCypher Response:\n")
                response_content = text[response_start:].strip()
                
                print("Generated Cypher Query:")
                print(query)
                print("\nCypher Response:")
                print(response_content)

            # Step 4: Query the knowledge graph
            response = query_engine.query(str(refined_question))
            print("\nResponse:")
            print(str(response))

if __name__ == "__main__":
    main()
