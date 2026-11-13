"""Minimal S-expression reader/writer for KiCad files.

Strings are kept as Str so they are written back with quotes.
"""


class Str(str):
    """A quoted string token."""


def parse(text):
    pos = 0
    n = len(text)

    def skip_ws():
        nonlocal pos
        while pos < n and text[pos] in " \t\r\n":
            pos += 1

    def read():
        nonlocal pos
        skip_ws()
        c = text[pos]
        if c == "(":
            pos += 1
            out = []
            while True:
                skip_ws()
                if text[pos] == ")":
                    pos += 1
                    return out
                out.append(read())
        if c == '"':
            pos += 1
            buf = []
            while True:
                ch = text[pos]
                if ch == "\\":
                    nxt = text[pos + 1]
                    buf.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
                    pos += 2
                    continue
                if ch == '"':
                    pos += 1
                    return Str("".join(buf))
                buf.append(ch)
                pos += 1
        start = pos
        while pos < n and text[pos] not in " \t\r\n()":
            pos += 1
        return text[start:pos]

    return read()


def _atom(x):
    if isinstance(x, Str):
        return '"' + x.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, float):
        s = f"{x:.4f}".rstrip("0").rstrip(".")
        return "0" if s in ("-0", "") else s
    return str(x)


def dump(node, indent=0):
    """Pretty-print: short lists on one line, longer ones split."""
    if not isinstance(node, list):
        return _atom(node)
    parts = [dump(c, indent + 1) for c in node]
    one = "(" + " ".join(parts) + ")"
    if len(one) <= 100 and "\n" not in one:
        return one
    pad = "\t" * (indent + 1)
    head = []
    rest = []
    for i, c in enumerate(node):
        if not rest and not isinstance(c, list) and i < 3:
            head.append(_atom(c))
        else:
            rest.append(dump(c, indent + 1))
    return "(" + " ".join(head) + "\n" + "\n".join(pad + r for r in rest) + "\n" + "\t" * indent + ")"


def find(node, key):
    """First child list whose head is key."""
    for c in node:
        if isinstance(c, list) and c and c[0] == key:
            return c
    return None


def find_all(node, key):
    return [c for c in node if isinstance(c, list) and c and c[0] == key]
