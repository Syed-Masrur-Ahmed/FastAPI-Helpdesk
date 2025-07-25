from sentence_transformers import SentenceTransformer, util
import torch

def find_similar_items_embeddings(phrase: str, all_items: list, top_n: int = 5):
    if not all_items:
        return []
    
    print("Loading sentence-transformer model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print("Model loaded.")

    corpus = [item.title + " " + item.question + " " + item.answer for item in all_items]

    print("Generating embeddings for database items...")
    corpus_embeddings = model.encode(corpus, convert_to_tensor=True)
    
    print("Generating embedding for the search phrase...")
    phrase_embedding = model.encode(phrase, convert_to_tensor=True)

    print("Calculating similarity scores...")
    cosine_scores = util.cos_sim(phrase_embedding, corpus_embeddings)

    top_results = torch.topk(cosine_scores, k=min(top_n, len(all_items)))

    similar_items = []
    print("\nTop similarity scores:")
    for score, idx in zip(top_results[0][0], top_results[1][0]):
        item_index = idx.item()
        print(f"  - Score: {score:.4f}, Item: '{all_items[item_index].question[:60]}...'")
        similar_items.append(all_items[item_index])

    return similar_items