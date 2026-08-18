"""Shared parsing helpers used across collectors."""

# Short-form result codes several sites use verbatim for their headline
# tip: "1"/"X"/"2" for 1X2, "1X"/"X2"/"12" for Double Chance.
TIP_CODE_MAP = {
    "1": ("1X2", "1"),
    "X": ("1X2", "X"),
    "2": ("1X2", "2"),
    "1X": ("Double Chance", "1X"),
    "X2": ("Double Chance", "X2"),
    "12": ("Double Chance", "12"),
}
