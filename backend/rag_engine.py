import os
import re
import math
from collections import Counter
from typing import List, Dict, Any

class PolicyChunk:
    def __init__(self, doc_title: str, category: str, section: str, content: str, file_path: str):
        self.doc_title = doc_title
        self.category = category
        self.section = section
        self.content = content
        self.file_path = file_path
        self.tokens = self._tokenize(f"{doc_title} {category} {section} {content}")
        self.tf = Counter(self.tokens)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        # Lowercase, clean punctuation, filter stopwords
        words = re.findall(r'[a-zA-Z0-9_\-\$]+', text.lower())
        stopwords = {
            "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "with",
            "is", "are", "was", "were", "of", "by", "as", "it", "this", "that", "be", "have"
        }
        return [w for w in words if len(w) > 1 and w not in stopwords]

class DiagnosticPolicyRAG:
    """
    High-performance, zero-external-dependency RAG engine designed specifically
    for diagnostic laboratory Standard Operating Procedures (SOPs), clinical panic values,
    fasting protocols, and cancellation/refund guidelines.
    """
    def __init__(self, policies_dir: str = None):
        if policies_dir is None:
            policies_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "policies")
        self.policies_dir = policies_dir
        self.chunks: List[PolicyChunk] = []
        self.idf: Dict[str, float] = {}
        self.load_and_index_policies()

    def load_and_index_policies(self):
        self.chunks = []
        if not os.path.exists(self.policies_dir):
            print(f"[RAG] Warning: Policies directory not found: {self.policies_dir}")
            return

        for fname in os.listdir(self.policies_dir):
            if fname.endswith(".md") or fname.endswith(".txt"):
                fpath = os.path.join(self.policies_dir, fname)
                self._index_file(fpath, fname)

        self._compute_idf()
        print(f"[RAG] Successfully indexed {len(self.chunks)} semantic policy chunks across diagnostic SOPs.")

    def _index_file(self, fpath: str, filename: str):
        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
            raw_text = f.read()

        # Extract title
        title_match = re.search(r'^#\s+(.+)$', raw_text, re.MULTILINE)
        doc_title = title_match.group(1).strip() if title_match else filename.replace("_", " ").title()

        # Categorize
        cat_match = re.search(r'Policy Reference:\s*([A-Z0-9\-]+)', raw_text)
        category = cat_match.group(1).strip() if cat_match else "General Laboratory SOP"

        # Split into sections by markdown headers ## or ###
        sections = re.split(r'\n(?=#{2,3}\s+)', raw_text)

        for sec in sections:
            sec_lines = sec.strip().split("\n")
            if not sec_lines:
                continue
            sec_header = sec_lines[0].replace("#", "").strip()
            sec_body = "\n".join(sec_lines[1:]).strip() if len(sec_lines) > 1 else sec_lines[0]
            # Skip pure document header / meta lines without clinical content
            if not sec_lines[0].startswith("##") and len(sec_lines) <= 3:
                continue
            if len(sec_body) < 25:
                continue

            chunk = PolicyChunk(
                doc_title=doc_title,
                category=category,
                section=sec_header,
                content=sec.strip(),
                file_path=os.path.basename(fpath)
            )
            self.chunks.append(chunk)

    def _compute_idf(self):
        total_docs = len(self.chunks)
        if total_docs == 0:
            return

        doc_counts = Counter()
        for chunk in self.chunks:
            for term in set(chunk.tokens):
                doc_counts[term] += 1

        self.idf = {
            term: math.log((total_docs + 1) / (count + 0.5)) + 1.0
            for term, count in doc_counts.items()
        }

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        if not self.chunks:
            self.load_and_index_policies()

        query_tokens = PolicyChunk._tokenize(query)
        if not query_tokens:
            return []

        query_tf = Counter(query_tokens)
        scores = []

        avg_len = sum(len(c.tokens) for c in self.chunks) / max(len(self.chunks), 1)

        for chunk in self.chunks:
            score = 0.0
            chunk_len = len(chunk.tokens)
            # BM25-style length normalization (b=0.4, k1=1.2)
            len_norm = 1.0 - 0.4 + 0.4 * (chunk_len / avg_len)

            for term, q_count in query_tf.items():
                if term in chunk.tf:
                    idf_val = self.idf.get(term, 1.0)
                    tf_chunk = chunk.tf[term]
                    # Specific/rare domain terms (high IDF) carry dominant weight
                    term_score = (tf_chunk * (idf_val ** 2.5)) / (tf_chunk + 1.2 * len_norm)
                    score += term_score

            # Substring / Exact content matching bonus for rare query terms
            chunk_text_lower = chunk.content.lower()
            for term in query_tokens:
                idf_val = self.idf.get(term, 1.0)
                if term in chunk_text_lower and idf_val > 2.0:
                    # Rare terms like troponin, ferritin, fasting get a massive direct boost
                    score += idf_val * 8.0

            clean_query = query.lower().strip()
            if clean_query in chunk_text_lower:
                score += 20.0

            if score > 0.05:
                scores.append((score, chunk))

        scores.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, chunk in scores[:top_k]:
            results.append({
                "score": round(score, 3),
                "title": chunk.doc_title,
                "category": chunk.category,
                "section": chunk.section,
                "content": chunk.content,
                "file_path": chunk.file_path
            })
        return results

    def answer_query(self, user_question: str) -> Dict[str, Any]:
        """
        Retrieves matching policy sections and generates an authoritative grounded answer.
        """
        results = self.search(user_question, top_k=2)
        if not results:
            return {
                "answer": "I could not find an exact clause in our official laboratory Standard Operating Procedures for that query. Please contact our Chief Pathologist or Helpdesk.",
                "citations": []
            }

        top_hit = results[0]
        summary_text = (
            f"According to Apex MediLab Policy ({top_hit['title']} - {top_hit['section']}):\n"
            f"{top_hit['content']}"
        )
        return {
            "answer": summary_text,
            "citations": [
                {"title": r["title"], "section": r["section"], "file": r["file_path"], "score": r["score"]}
                for r in results
            ]
        }

# Singleton RAG instance
rag_engine = DiagnosticPolicyRAG()
