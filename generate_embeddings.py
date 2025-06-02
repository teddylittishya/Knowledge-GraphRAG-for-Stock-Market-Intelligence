import json
import torch
import dgl
from dgl.nn import TransE
from neo4j import GraphDatabase
import pandas as pd
import numpy as np
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt

# Neo4j connection parameters
NEO4J_URI = "bolt://localhost:7687"  # Adjust if your Neo4j instance uses a different port
NEO4J_USER = "neo4j"                 # Replace with your Neo4j username
NEO4J_PASSWORD = "prahar@156"          # Replace with your Neo4j password

# Graph parameters for DGL
embedding_dim = 100
learning_rate = 0.01
epochs = 1000

# Connect to Neo4j
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def fetch_graph_data():
    with driver.session() as session:
        # Fetch all nodes
        node_query = "MATCH (n) RETURN elementId(n) AS node_id"
        nodes_result = session.run(node_query)
        nodes = [record["node_id"] for record in nodes_result]

        # Fetch all relationships
        edge_query = "MATCH (n)-[r]->(m) RETURN elementId(n) AS source_id, elementId(m) AS target_id, type(r) AS relation"
        edges_result = session.run(edge_query)
        edges = [(record["source_id"], record["target_id"], record["relation"]) for record in edges_result]

    # Display edges as a DataFrame
    df_edges = pd.DataFrame(edges, columns=['source', 'target', 'relation'])
    print("Extracted Relationships:")
    print(df_edges.head())

    return nodes, edges

def train_embeddings(nodes, edges):
    # Map nodes and relations to unique IDs
    node_to_id = {node: idx for idx, node in enumerate(nodes)}
    relation_to_id = {rel: idx for idx, rel in enumerate(set(e[2] for e in edges))}

    # Prepare edge lists
    source_ids = [node_to_id[edge[0]] for edge in edges]
    target_ids = [node_to_id[edge[1]] for edge in edges]
    relation_ids = [relation_to_id[edge[2]] for edge in edges]

    # Create DGL graph
    g = dgl.graph((source_ids, target_ids))

    # Initialize TransE model
    model = TransE(num_rels=len(relation_to_id), feats=embedding_dim)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)

    # Initialize node embeddings
    node_embeddings = torch.nn.Embedding(len(nodes), embedding_dim)
    torch.nn.init.xavier_uniform_(node_embeddings.weight)

    # Training loop
    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()

        # Get embeddings for source and target nodes
        h_head = node_embeddings(torch.tensor(source_ids))
        h_tail = node_embeddings(torch.tensor(target_ids))
        rels = torch.tensor(relation_ids)

        # Compute loss
        loss = model(h_head, h_tail, rels).mean()
        loss.backward()
        optimizer.step()

        if epoch % 10 == 0:
            print(f"Epoch {epoch}/{epochs}, Loss: {loss.item()}")

    # Extract embeddings
    entity_embeddings = node_embeddings.weight.data.numpy()
    return entity_embeddings, node_to_id

def update_embeddings_in_neo4j(embeddings, node_to_id):
    reverse_node_to_id = {idx: node for node, idx in node_to_id.items()}
    with driver.session() as session:
        for idx, embedding in enumerate(embeddings):
            node_id = reverse_node_to_id[idx]
            embedding_list = embedding.tolist()
            # Update the node with the embedding
            session.run(
                "MATCH (n) WHERE elementId(n) = $node_id SET n.embedding = $embedding",
                node_id=node_id,
                embedding=embedding_list
            )

def main():
    # Fetch nodes and edges from Neo4j
    nodes, edges = fetch_graph_data()

    # Train embeddings
    embeddings, node_to_id = train_embeddings(nodes, edges)

    # Update Neo4j with embeddings
    update_embeddings_in_neo4j(embeddings, node_to_id)

if __name__ == "__main__":
    main()


from llama_index.core.schema import TextNode
from neo4j import GraphDatabase

# # Function to clear old embeddings in the vector store
# def clear_old_embeddings(vector_store):
#     print("Clearing old embeddings from the vector store...")
#     vector_store.adelete([])  
#     print("Old embeddings cleared.")

# # Function to fetch nodes from Neo4j
# def fetch_nodes(tx, label, property_key):
#     query = f"""
#     MATCH (n:{label}) RETURN n.{property_key} AS text, elementId(n) AS id, n.name as name
#     """
#     result = tx.run(query)
#     return [{"id": record["id"], "name": record["name"], "text": record["text"]} for record in result]

# # Main workflow
# with driver.session() as session:
#     # Step 1: Clear old embeddings
#     clear_old_embeddings(vector_store)

#     # Step 2: Fetch nodes from Neo4j
#     label = "Company"  # Replace with your node label
#     property_key = "business_summary"  # Replace with the property you want to embed

#     nodes = session.read_transaction(fetch_nodes, label, property_key)
#     print(f"Fetched {len(nodes)} nodes.")

#     text_nodes = []

#     for node in nodes:
#         node_id = node["id"]
#         text = f"""({node["id"]}) {node["name"]}: {node["text"]}"""

#         if text:
#             # Generate embedding for the text
#             embedding = embed_model.get_text_embedding(text)
#             print(f"Generated embedding for node {node_id}")

#             # Create a TextNode object for the vector store
#             text_node = TextNode(
#                 id_=node_id,
#                 text=text,
#                 embedding=embedding,
#                 metadata={"name": node["name"]},
#             )
#             text_nodes.append(text_node)

#     # Step 3: Add TextNodes to the Neo4jVectorStore using the updated procedure
#     print("Inserting new embeddings into the vector store...")
#     vector_store.add(text_nodes)
#     print("Embeddings stored in vector store.")

# print("Workflow complete.")