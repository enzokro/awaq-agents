"""Embedding utilities."""

import time
from typing import Union
from pathlib import Path
from fastcore.xtras import *
from framework.documents import load_docling
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer
from sentence_transformers.util import cos_sim
import numpy as np
from docling_core.transforms.chunker import HierarchicalChunker, BaseChunker
from docling_core.types.doc.document import DoclingDocument

# --- Configuration ---
ARTIFACTS_DIR = Path("/Users/cck/projects/cck-agents/artifacts")
EMBEDDING_MODEL_NAME = 'nomic-ai/modernbert-embed-base'  # Efficient local model
MAX_LEN = 8192

DEVICE = ("cuda" if torch.cuda.is_available() else 
         ("mps"  if torch.backends.mps.is_available() else 
          "cpu"))


class EmbeddingsLoader:
    def __init__(self):
        self.file_id = None
        self.chunks = None
        self.embeddings = None

    def set_file_id(self, file_id: str):
        self.file_id = file_id

    def load(self):
        """Load the embeddings from the file."""
        if not self.file_id:
            raise ValueError("File ID not set")
        if (not self.chunks) and (not self.embeddings):
            self.embeddings_path = Path(f"{ARTIFACTS_DIR}/{self.file_id}/embeddings/late_chunks.npz")
            embeddings = np.load(self.embeddings_path)
            self.chunks = embeddings['chunks']
            self.embeddings = embeddings['embeddings']

RAGEmbeds = EmbeddingsLoader()

def flatten_meta(meta):
    """Flatten the meta data into a single string."""
    return "\n".join([f"{k}: {v}" for k, v in meta.items()])

# def chunk_docling_md(
#         doc,
#         chunker_cls: BaseChunker = HierarchicalChunker
#     ):
#     texts, metas = [], []

#     # extract useful metadata for the embeds
#     meta_fields = [
#         'parent',
#         'children',
#         'content_layer',
#         'label',
#     ]
#     chunker = chunker_cls()

#     # Process each document in the list
#     chunks = list(chunker.chunk(doc))  

#     # Get useful meta-data from each chunk
#     for idx, chunk in enumerate(chunks):
#         # need to label the chunk to know where it comes from
#         meta = {'chunk_id': idx}

#         # add the original filenanme for sanity
#         meta.update({'file': str(chunk.meta.origin.filename)})

#         # process the docling metadata
#         itms = chunk.meta.doc_items
#         for itm in itms:
#             meta.update({k: str(getattr(itm, k)) for k in meta_fields})

#             # add the provenance info as string, might help?
#             prov = chunk.meta.doc_items[0].prov
#             for i,p in enumerate(prov):
#                 meta.update({
#                     f'prov_{i}_page_number': p.page_no,
#                     f'prov_{i}_bounding_box': str(p.bbox)
#                 })

#         metas.append(meta)
#         texts.append(chunk.text)

#     return texts, metas


def mean_pooling(model_output, attention_mask):
    token_embeddings = model_output[0]
    input_mask_expanded = (
        attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
    )
    return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
        input_mask_expanded.sum(1), min=1e-9
    )


def embed_docling_json(docling_src: Union[DoclingDocument, Path], output_dir: Path):

    if isinstance(docling_src, Path):
        # load the docling json
        doc = load_docling(docling_src)
    else:
        doc = docling_src

    # make sure the output directory 
    output_dir.mkdir(parents=True, exist_ok=True)

    # get the full text
    text = doc.export_to_text()

    # load the models
    print(f"Loading model: {EMBEDDING_MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(EMBEDDING_MODEL_NAME)
    model = AutoModel.from_pretrained(EMBEDDING_MODEL_NAME)

    # get the embeddings and chunks
    print("Chunking document...")
    late_chunks, late_embeds = late_chunking(text, model, tokenizer)

    # save the embeddings and chunks
    np.savez(output_dir / f"late_chunks.npz", chunks=late_chunks, embeddings=late_embeds)

    return late_chunks, late_embeds


def late_chunking(document, model, tokenizer):
    "Implements late chunking on a document."

    # Tokenize with offset mapping to find sentence boundaries
    inputs_with_offsets = tokenizer(
        document,
        return_tensors='pt',
        return_offsets_mapping=True,
        truncation=True,
        max_length=MAX_LEN,
    )
    token_offsets = inputs_with_offsets['offset_mapping'][0]
    token_ids = inputs_with_offsets['input_ids'][0]
    
    # Find chunk boundaries
    punctuation_mark_id = tokenizer.convert_tokens_to_ids('.')    
    chunk_positions, token_span_annotations = [], []
    span_start_char, span_start_token = 0, 0

    for i, (token_id, (start, end)) in enumerate(zip(token_ids, token_offsets)):
        if i < len(token_ids)-1:
            if token_id == punctuation_mark_id and document[end:end+1] in [' ', '\n']:
                # Store both character positions and token positions
                chunk_positions.append((span_start_char, int(end)))
                token_span_annotations.append((span_start_token, i+1))
                
                # Update start positions for next chunk
                span_start_char, span_start_token = int(end)+1, i+1
    
    # Create text chunks from character positions
    chunks = [document[start:end].strip() for start, end in chunk_positions]
    
    # Encode the entire document
    inputs = tokenizer(
        document,
        return_tensors='pt',
        truncation=True,
        max_length=MAX_LEN,
    )
    model_output = model(**inputs)
    token_embeddings = model_output[0]
    
    # Create embeddings for each chunk using mean pooling
    embeddings = []
    for start_token, end_token in token_span_annotations:
        if end_token > start_token:  # Ensure span has at least one token
            chunk_embedding = token_embeddings[0, start_token:end_token].mean(dim=0)
            embeddings.append(chunk_embedding.detach().cpu().numpy())

    embeddings = np.stack(embeddings)
    
    return chunks, embeddings


def load_models(model_name: str):
    """Load the model from a file."""
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModel.from_pretrained(model_name)
    return tokenizer, model


def matched_late_retrieval(
        query,
        chunks,
        chunk_embeddings,
        tokenizer,
        model,
        top_k=2,
    ):
    """Retrieve the most relevant chunk for a query."""

    # embed the query, pooling as we did the chunks
    query_tokens = tokenizer(query, return_tensors='pt')
    query_embeddings = model(**query_tokens)
    query_embedding = mean_pooling(query_embeddings, query_tokens['attention_mask'])
    
    # find similarities between query and chunks
    similarities = cos_sim(query_embedding, chunk_embeddings).detach().cpu().numpy().squeeze()
    
    # sort the most similar chunks
    top_idx = np.argsort(similarities)[::-1][:top_k]

    # get the top chunks and their similarities
    top_chunks = [chunks[i] for i in top_idx]
    top_sims = [similarities[i] for i in top_idx]
    
    return top_chunks, top_sims


def load_embeddings(embeddings_path: Path):
    """Load the embeddings from a file."""
    return np.load(embeddings_path)
