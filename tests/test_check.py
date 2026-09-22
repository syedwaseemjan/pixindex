from __future__ import annotations

from color_embedder import ColorEmbedder
from pixindex.check import format_check, run_check


def test_builtin_examples_pass_with_the_stand_in_model() -> None:
    report = run_check(ColorEmbedder())
    assert report.ok
    assert format_check(report) == "Picture search: 2/2\nDuplicates: 1/1"
