"""Optional corpus-collocation score for reranking."""
import json, math, re
from pathlib import Path

_WORD = re.compile(r"[a-zà-ỹđ]+", re.I)

def words(text):
    return _WORD.findall(text.lower())

class CollocationScorer:
    def __init__(self, unigram, bigram, alpha=0.1):
        self.unigram, self.bigram, self.alpha = unigram, bigram, alpha
        self.vocabulary = max(1, len(unigram))
    @classmethod
    def load(cls, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data["unigram"], data["bigram"], data.get("alpha", 0.1))
    def raw_score(self, poem):
        pairs = []
        for line in poem.splitlines():
            row = words(line); pairs.extend(zip(row, row[1:]))
        if not pairs: return None
        values = []
        for left, right in pairs:
            p = (self.bigram.get(f"{left}\t{right}", 0) + self.alpha) / (self.unigram.get(left, 0) + self.alpha * self.vocabulary)
            values.append(math.log(p))
        return sum(values) / len(values)
    def score(self, poem):
        raw = self.raw_score(poem)
        return 0.0 if raw is None else max(0.0, min(1.0, (raw + 12.0) / 8.0))
