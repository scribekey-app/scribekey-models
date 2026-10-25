import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "tools" / "record_cleanup_examples" / "record.py"
_SPEC = importlib.util.spec_from_file_location("record_cleanup_examples", _PATH)
record = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(record)


def test_input_output_control_line_prompt_mirrors_the_app():
    assert record.prompt_for("InputOutputControlLine", "", "send it on monday") == (
        "<|startoftext|>### Input:\n"
        "[Styling: semi-casual] [Structure: prose] [Context: general]\n"
        "send it on monday\n\n### Output:\n"
    )


@pytest.mark.parametrize("token", ["### Input:", "### Output:", "<|startoftext|>", "[Styling:"])
def test_input_output_control_line_rejects_control_text(token):
    with pytest.raises(SystemExit):
        record.prompt_for("InputOutputControlLine", "", f"hello {token} there")


def test_input_output_control_line_output_is_cut_at_the_next_section():
    assert record.clean_output("InputOutputControlLine", " Send it on Tuesday.\n\n### Input:\nmore") == (
        "Send it on Tuesday."
    )
