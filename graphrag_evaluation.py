from sklearn.metrics import precision_score, recall_score
from nltk.translate.bleu_score import sentence_bleu
from rouge_score import rouge_scorer
from bert_score import score as bert_score
import pandas as pd
import numpy as np

# Load the dataset
file_path = 'testset.csv'
data = pd.read_csv(file_path)

# Helper functions for metrics
def compute_retrieval_metrics(retrieved, relevant, k):
    retrieved_set = set(retrieved[:k])
    relevant_set = set(relevant)
    
    # Precision@K
    precision = len(retrieved_set & relevant_set) / len(retrieved_set) if len(retrieved_set) > 0 else 0
    
    # Recall@K
    recall = len(retrieved_set & relevant_set) / len(relevant_set) if len(relevant_set) > 0 else 0
    
    # MRR (Mean Reciprocal Rank)
    mrr = 0
    for rank, node in enumerate(retrieved, start=1):
        if node in relevant_set:
            mrr = 1 / rank
            break
    
    return precision, recall, mrr

def compute_generation_metrics(predicted, ground_truth):
    from torch import tensor

    # BLEU Score
    bleu = sentence_bleu([ground_truth.split()], predicted.split())
    
    # ROUGE Score
    rouge = rouge_scorer.RougeScorer(['rouge1', 'rougeL'], use_stemmer=True)
    rouge_scores = rouge.score(ground_truth, predicted)
    
    # BERTScore
    bert = bert_score([predicted], [ground_truth], lang="en")
    bert_mean = bert[2].mean().item()  # Convert Tensor to scalar
    
    return bleu, rouge_scores['rouge1'].fmeasure, rouge_scores['rougeL'].fmeasure, bert_mean

# Process the data and calculate metrics
results = []
k = 2  # Define K for Precision@K and Recall@K

for _, row in data.iterrows():
    # Retrieve and split relevant and retrieved node IDs
    relevant_ids = str(row['relevant_node_ids']).split(', ')
    retrieved_ids = str(row['retrieved_node_ids']).split(', ')
    
    # Compute retrieval metrics
    precision, recall, mrr = compute_retrieval_metrics(retrieved_ids, relevant_ids, k)
    
    # Compute generation metrics
    bleu, rouge1, rougeL, bert = compute_generation_metrics(str(row['generated_answer']), str(row['true_answer']))
    
    # Append results
    results.append({
        "Question": row['question'],
        "Precision@K": round(precision, 2),
        "Recall@K": round(recall, 2),
        "MRR": round(mrr, 2),
        "ROUGE-1": round(rouge1, 2),
        "ROUGE-L": round(rougeL, 2),
        "BERTScore": round(bert, 2)
    })

# Convert results to a DataFrame for visualization
results_df = pd.DataFrame(results)

# Save results to a CSV file
output_file = 'evaluation_metrics_results.csv'
results_df.to_csv(output_file, index=False)