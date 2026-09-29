"""A sort key that handles embedded numbers the way people expect."""


def natural_sort_key(text: str) -> list[str]:
    """A sort key for `text` in which numbers compare as numbers, everything else case-insensitively:
    "NGC 9" before "NGC 10".

    :param text: the text to build a sort key for
    :returns: the sort key, comparable with that of another call
    """
    key: list[str] = []
    chunk = ""
    digits: bool | None = None
    for character in text:
        is_digit = character.isdigit()
        if digits is None:
            digits = is_digit
        if is_digit == digits:
            chunk += character
            continue
        key.append(f"{int(chunk):010d}" if digits else chunk.lower())
        chunk, digits = character, is_digit
    if chunk:
        key.append(f"{int(chunk):010d}" if digits else chunk.lower())
    return key
