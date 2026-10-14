import os
import sys
import math
import re
import sqlite3
import argparse
from typing import Dict, List, Tuple, Optional, Set

def _log_telemetry(err: Exception, context: str = "") -> None:
    """Non-fatal telemetry catch for degraded operations."""
    if os.environ.get("ORION_DEBUG"):
        msg = f": {err}" if err else ""
        sys.stderr.write(f"[ORION_TELEMETRY] Non-fatal catch in {context}{msg}\n")


if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception as _e:
        _log_telemetry(_e, 'compactor.py:reconfigure')


PRESERVE_WORDS: Set[str] = {
    "not", "no", "never", "none", "neither", "nor", "cannot", "without",
    "true", "false", "null", "if", "else", "return", "error", "fail", "pass"
}


class CorpusInformationCompactor:
    """
    Pillar 1: Information-Theoretic Context Compactor.
    Distilled from LLMLingua & Caveman.
    Calculates statistical self-information I(w) = -log2 P(w) via SQLite3 fts5vocab
    and prunes low-surprisal linguistic filler while preserving syntax boundaries and code blocks.
    """

    def __init__(self, db_path: Optional[str] = None):
        if not db_path:
            workspace_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            orion_dir = os.path.join(workspace_root, ".orion")
            if os.path.isdir(orion_dir):
                self.db_path = os.path.join(orion_dir, "compactor.db")
            else:
                self.db_path = ":memory:"
        else:
            self.db_path = db_path

        self.conn = sqlite3.connect(self.db_path)
        self._total_corpus_terms: Optional[int] = None
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensures fts5 and fts5vocab tables exist for term frequency calculation."""
        try:
            with self.conn:
                self.conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS compactor_corpus USING fts5(
                        content,
                        tokenize = 'unicode61'
                    );
                """)
                self.conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS compactor_vocab USING fts5vocab(
                        compactor_corpus,
                        row
                    );
                """)
        except Exception as e:
            _log_telemetry(e, "compactor.py:_ensure_schema")

    def index_text(self, text: str) -> None:
        """Adds text into the corpus to build vocabulary statistics."""
        if not text.strip():
            return
        try:
            with self.conn:
                self.conn.execute("INSERT INTO compactor_corpus(content) VALUES (?)", (text,))
            self._total_corpus_terms = None
        except Exception as e:
            _log_telemetry(e, "compactor.py:index_text")

    def get_total_terms(self) -> int:
        """Returns total term occurrences across the corpus."""
        if self._total_corpus_terms is not None:
            return self._total_corpus_terms

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT sum(cnt) FROM compactor_vocab")
            row = cur.fetchone()
            total = row[0] if (row and row[0]) else 0
            self._total_corpus_terms = max(total, 1)
            return self._total_corpus_terms
        except Exception as e:
            _log_telemetry(e, "compactor.py:get_total_terms")
            return 1

    def calculate_surprisal(self, word: str) -> float:
        """
        Calculates Shannon self-information / surprisal:
        I(w) = -log2( P(w) ), where P(w) = cnt(w) / N
        High surprisal = rare/salient word. Low surprisal = common/filler word.
        """
        clean_word = re.sub(r"[^\w]", "", word).lower()
        if not clean_word:
            return 0.0

        if clean_word in PRESERVE_WORDS:
            return 20.0  # Force retention of semantic negations and boolean invariants

        try:
            cur = self.conn.cursor()
            cur.execute("SELECT cnt FROM compactor_vocab WHERE term = ?", (clean_word,))
            row = cur.fetchone()
            if not row or not row[0]:
                return 14.0  # Out-of-vocabulary / rare domain term has high information

            cnt = row[0]
            total = self.get_total_terms()
            prob = max(cnt / total, 1e-6)
            return -math.log2(prob)
        except Exception as e:
            _log_telemetry(e, f"compactor.py:calculate_surprisal:{word}")
            return 10.0

    def compact(self, text: str, keep_ratio: float = 0.6, preserve_code: bool = True) -> str:
        """
        Prunes low-surprisal words to hit keep_ratio target while preserving
        code fences, Markdown headers, table rows, and syntactic anchors.
        """
        if keep_ratio >= 1.0 or not text.strip():
            return text

        lines = text.split("\n")
        compacted_lines: List[str] = []
        in_code_block = False

        for line in lines:
            stripped = line.strip()
            # 1. Structural anchors: Markdown code blocks
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                compacted_lines.append(line)
                continue

            if in_code_block and preserve_code:
                compacted_lines.append(line)
                continue

            # 2. Structural anchors: Headers, list markers, table dividers
            if stripped.startswith(("#", "-", "*", ">", "|", "1.", "2.", "3.", "4.", "5.")):
                # Keep anchor prefix untouched, compact line remainder
                parts = line.split(" ", 1)
                if len(parts) == 2:
                    prefix, content = parts[0], parts[1]
                    compacted_remainder = self._compact_sentence(content, keep_ratio)
                    compacted_lines.append(f"{prefix} {compacted_remainder}")
                    continue
                compacted_lines.append(line)
                continue

            # 3. Standard prose compaction
            compacted_lines.append(self._compact_sentence(line, keep_ratio))

        return "\n".join(compacted_lines)

    def _compact_sentence(self, sentence: str, keep_ratio: float) -> str:
        words = sentence.split()
        if len(words) <= 5:
            return sentence

        scored_tokens: List[Tuple[int, str, float]] = []
        for idx, w in enumerate(words):
            # Inline code or symbols
            if w.startswith("`") or w.endswith("`") or any(char in w for char in "{}[]()=<>"):
                surprisal = 25.0
            else:
                surprisal = self.calculate_surprisal(w)
            scored_tokens.append((idx, w, surprisal))

        target_count = max(3, int(math.ceil(len(words) * keep_ratio)))
        # Sort by surprisal descending
        ranked = sorted(scored_tokens, key=lambda x: x[2], reverse=True)
        # Select top target_count tokens
        selected_indices = {item[0] for item in ranked[:target_count]}

        # Reconstruct in original chronological order
        result_words = [words[i] for i in range(len(words)) if i in selected_indices]
        return " ".join(result_words)


def main():
    parser = argparse.ArgumentParser(description="Pillar 1: Information-Theoretic Context Compactor")
    parser.add_argument("--text", type=str, help="Prose string to compact")
    parser.add_argument("--file", type=str, help="Path to text or markdown file to compact")
    parser.add_argument("--ratio", type=float, default=0.6, help="Target retention ratio (0.1 to 1.0)")
    parser.add_argument("--index", type=str, help="Index text into corpus before compaction")
    args = parser.parse_args()

    compactor = CorpusInformationCompactor()

    if args.index:
        compactor.index_text(args.index)
        print(f"[COMPACTOR] Indexed {len(args.index.split())} terms into corpus vocab.")

    input_text = ""
    if args.text:
        input_text = args.text
    elif args.file and os.path.isfile(args.file):
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            input_text = f.read()

    if not input_text:
        if len(sys.argv) == 1:
            parser.print_help()
            sys.exit(0)
        print("Error: No input text provided via --text or --file.", file=sys.stderr)
        sys.exit(1)

    result = compactor.compact(input_text, keep_ratio=args.ratio)
    orig_words = len(input_text.split())
    comp_words = len(result.split())
    saved_pct = ((orig_words - comp_words) / orig_words * 100.0) if orig_words > 0 else 0.0

    print(f"[COMPACTION SUMMARY] Original: {orig_words} words | Compacted: {comp_words} words | Savings: {saved_pct:.1f}%")
    print("--------------------------------------------------------------------------------")
    print(result)


if __name__ == "__main__":
    main()
