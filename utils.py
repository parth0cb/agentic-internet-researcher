import datetime
import requests
import re
import bleach
import torch

from ddgs import DDGS
import trafilatura

from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer


tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L12-v2")
model = SentenceTransformer("all-MiniLM-L12-v2")

def gather_contextual_info():
    utc_now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    try:
        response = requests.get("https://ipinfo.io/json")
        response.raise_for_status()
        data = response.json()
        
        city = data.get("city", "Unknown city")
        region = data.get("region", "Unknown region")
        country = data.get("country", "Unknown country")
    except requests.RequestException:
        city = region = country = loc = "Unavailable"
    
    info_str = (
        "Contextual Information:"
        f"Date & Time (UTC): {utc_now}\n"
        f"Approximate Location: {city}, {region}, {country}\n---\n\n"
    )
    
    return info_str

def ensure_scheme(url):
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url


def get_top_urls(query, num_results=10):
    with DDGS() as ddgs:
        try:
            results = ddgs.text(query, max_results=num_results)
            urls = [r["href"] for r in results]
            return urls
        except Exception:
            return []


def get_chunks_from_urls(urls, number_of_urls=10):
    chunk_size = 256
    overlap = 64
    all_chunks = []
    successful_fetches = 0
    url_index = 0

    while successful_fetches < number_of_urls and url_index < len(urls):
        url = ensure_scheme(urls[url_index])
        url_index += 1

        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                content = trafilatura.extract(downloaded)
                if content:
                    tokens = tokenizer.encode(content, add_special_tokens=False)
                    i = 0
                    while i < len(tokens):
                        chunk = tokens[i : i + chunk_size]
                        if chunk:
                            decoded_chunk = tokenizer.decode(
                                chunk, skip_special_tokens=True
                            )
                            chunk_with_source = f"{decoded_chunk}\nSource: {url}"
                            all_chunks.append(chunk_with_source)
                        i += chunk_size - overlap
                    successful_fetches += 1
        except Exception as e:
            continue

    if not all_chunks:
        print("No content was extracted from links")

    return all_chunks



def get_top_chunks(query, chunks, number_of_top_chunks=5):
    query_embedding = model.encode(query, convert_to_tensor=True)
    chunk_embeddings = model.encode(chunks, convert_to_tensor=True)
    similarities = util.cos_sim(query_embedding, chunk_embeddings)[0]
    top_indices = torch.topk(similarities, number_of_top_chunks).indices
    top_chunks = [chunks[i] for i in top_indices]
    return top_chunks


def escape_outside_inline_code(line):
    parts = re.split(r'(`[^`]*`)', line)  
    for i, part in enumerate(parts):
        if not part.startswith('`'):  
            parts[i] = bleach.clean(part)
    return ''.join(parts)


def escape_outside_code_blocks(text):
    result = []
    in_fenced_block = False
    fenced_delim = "```"

    for line in text.splitlines():
        if line.strip().startswith(fenced_delim):
            in_fenced_block = not in_fenced_block
            result.append(line)
            continue

        if not in_fenced_block:
            
            line = escape_outside_inline_code(line)
        result.append(line)

    return '\n'.join(result)
