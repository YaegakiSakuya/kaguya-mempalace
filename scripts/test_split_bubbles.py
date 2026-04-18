"""Unit tests for _split_reply_into_bubbles.

Run directly:

    python scripts/test_split_bubbles.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

# Load only the function under test without importing the full module graph,
# so the test runs even when the runtime deps (openai, mcp, etc.) aren't
# installed in the current shell.
ROOT = Path(__file__).resolve().parent.parent
CLIENT_PATH = ROOT / "app" / "llm" / "client.py"

_src = CLIENT_PATH.read_text(encoding="utf-8")
_start = _src.index("_FENCE_RE = ")
_end = _src.index("def build_reply_system_prompt")
_snippet = "from __future__ import annotations\nimport re\n\n" + _src[_start:_end]

_mod_spec = importlib.util.spec_from_loader("client_bubbles_under_test", loader=None)
_mod = importlib.util.module_from_spec(_mod_spec)
exec(compile(_snippet, str(CLIENT_PATH), "exec"), _mod.__dict__)
sys.modules["client_bubbles_under_test"] = _mod

_split_reply_into_bubbles = _mod._split_reply_into_bubbles


def _assert(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(f"FAIL: {label}")
    print(f"PASS: {label}")


def test_empty_string() -> None:
    result = _split_reply_into_bubbles("")
    _assert(result == [], "empty string returns empty list")

    result = _split_reply_into_bubbles("   \n\n   ")
    _assert(result == [], "whitespace-only string returns empty list")


def test_single_paragraph() -> None:
    text = "这是一段完整的话，里面没有空行，应该只产生一个气泡。"
    result = _split_reply_into_bubbles(text)
    _assert(len(result) == 1, "single paragraph -> one bubble")
    _assert(result[0] == text, "single paragraph content preserved")


def test_three_paragraphs() -> None:
    text = (
        "第一段话的内容要足够长，至少需要超过二十个字符，这样它就不会被合并规则吞掉。\n\n"
        "第二段话的内容同样需要足够长，至少超过二十个字符才能独立成为一个气泡。\n\n"
        "第三段话的内容也要足够长，至少超过二十个字符才能独立成为一个气泡。"
    )
    result = _split_reply_into_bubbles(text)
    _assert(len(result) == 3, f"three paragraphs -> three bubbles (got {len(result)})")


def test_short_trailing_merged() -> None:
    text = "这是足够长的第一段内容，长度一定超过二十个字符。\n\n这是足够长的第二段内容，同样超过二十字符门槛。\n\n嗯。"
    result = _split_reply_into_bubbles(text)
    _assert(len(result) == 2, f"short trailing paragraph merged (got {len(result)})")
    _assert("嗯。" in result[-1], "short trailing content merged into previous bubble")
    _assert("嗯。" not in result[0], "short trailing content not in first bubble")


def test_code_block_preserved() -> None:
    text = (
        "这是代码前的引言段落，足够长。\n\n"
        "```python\n"
        "def foo():\n"
        "\n"
        "    return 1\n"
        "```\n\n"
        "这是代码后的说明段落，足够长。"
    )
    result = _split_reply_into_bubbles(text)
    joined = "\n\n".join(result)
    _assert("```python" in joined, "code fence start preserved")
    _assert("```" in result[1] if len(result) > 1 else "```" in result[0], "code block present in output")
    # Ensure the code block is intact within a single bubble (not split across bubbles).
    code_bubbles = [b for b in result if "```" in b]
    _assert(len(code_bubbles) == 1, f"code block stays in a single bubble (got {len(code_bubbles)})")
    _assert(code_bubbles[0].count("```") == 2, "both fence markers in same bubble")


def test_standalone_code_block_not_merged() -> None:
    """Regression: a standalone fenced code block between two long paragraphs
    should stay in its own bubble. The earlier implementation measured chunk
    length on the stashed placeholder (~10 chars), so the code block always
    merged into the previous paragraph."""
    text = (
        "这是代码前的足够长的引言段落，内容很长很长超过二十字符门槛没问题。\n\n"
        "```python\n"
        "def foo():\n"
        "    return 1\n"
        "```\n\n"
        "这是代码后的足够长的说明段落，内容很长很长超过二十字符门槛没问题。"
    )
    result = _split_reply_into_bubbles(text)
    _assert(len(result) == 3, f"code block stays in its own bubble (got {len(result)})")
    _assert("```" not in result[0], "code fence not merged into leading paragraph")
    _assert(result[1].startswith("```") and result[1].endswith("```"), "code block is the standalone middle bubble")
    _assert("```" not in result[2], "code fence not in trailing paragraph")


def test_long_paragraph_split() -> None:
    long_text = "a" * 5000
    result = _split_reply_into_bubbles(long_text)
    _assert(len(result) >= 2, f"long paragraph split into multiple bubbles (got {len(result)})")
    for i, bubble in enumerate(result):
        _assert(len(bubble) <= 3800, f"bubble {i} under max_len (got {len(bubble)})")
    _assert("".join(result) == long_text, "hard-sliced content round-trips")


def test_long_paragraph_with_sentences() -> None:
    sentence = "这是一句含有完整标点的测试句子。" * 500
    result = _split_reply_into_bubbles(sentence)
    _assert(len(result) >= 2, f"long sentence-rich text split (got {len(result)})")
    for i, bubble in enumerate(result):
        _assert(len(bubble) <= 3800, f"bubble {i} under max_len (got {len(bubble)})")


def main() -> int:
    tests = [
        test_empty_string,
        test_single_paragraph,
        test_three_paragraphs,
        test_short_trailing_merged,
        test_code_block_preserved,
        test_standalone_code_block_not_merged,
        test_long_paragraph_split,
        test_long_paragraph_with_sentences,
    ]
    failures = 0
    for test in tests:
        try:
            test()
        except AssertionError as exc:
            failures += 1
            print(exc)
    if failures:
        print(f"\n{failures} test(s) failed")
        return 1
    print("\nAll tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
