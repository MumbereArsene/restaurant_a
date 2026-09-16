"""Compile locale/en/LC_MESSAGES/django.po to django.mo (UTF-8)."""

from __future__ import annotations

import struct
from pathlib import Path


def _unquote(value: str) -> str:
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        value = value[1:-1]
    return bytes(value, "utf-8").decode("unicode_escape")


def parse_po(text: str) -> dict[str, str]:
    catalog: dict[str, str] = {"": "Content-Type: text/plain; charset=UTF-8\n"}
    msgid = msgstr = None
    in_id = in_str = False

    def flush() -> None:
        nonlocal msgid, msgstr
        if msgid is not None and msgstr is not None:
            catalog[msgid] = msgstr
        msgid = msgstr = None

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("msgid "):
            flush()
            msgid = _unquote(line[6:])
            in_id, in_str = True, False
        elif line.startswith("msgstr "):
            msgstr = _unquote(line[7:])
            in_id, in_str = False, True
        elif line.startswith('"') and (in_id or in_str):
            part = _unquote(line)
            if in_id:
                msgid = (msgid or "") + part
            else:
                msgstr = (msgstr or "") + part
    flush()
    if "" not in catalog or "charset" not in catalog[""].lower():
        catalog[""] = "Content-Type: text/plain; charset=UTF-8\n"
    return catalog


def write_mo(catalog: dict[str, str], dest: Path) -> None:
    ids = sorted(catalog.keys(), key=lambda item: item.encode("utf-8"))
    encoded_ids = [item.encode("utf-8") + b"\x00" for item in ids]
    encoded_str = [catalog[item].encode("utf-8") + b"\x00" for item in ids]
    keystart = 7 * 4 + 16 * len(ids)
    valuestart = keystart + sum(len(item) for item in encoded_ids)
    koffsets: list[tuple[int, int]] = []
    offset = 0
    for item in encoded_ids:
        koffsets.append((len(item) - 1, keystart + offset))
        offset += len(item)
    voffsets: list[tuple[int, int]] = []
    offset = 0
    for item in encoded_str:
        voffsets.append((len(item) - 1, valuestart + offset))
        offset += len(item)
    out = struct.pack("<Iiiiiii", 0x950412DE, 0, len(ids), 28, 28 + 8 * len(ids), 0, 0)
    for length, off in koffsets:
        out += struct.pack("<II", length, off)
    for length, off in voffsets:
        out += struct.pack("<II", length, off)
    dest.write_bytes(out + b"".join(encoded_ids) + b"".join(encoded_str))


def main() -> None:
    po = Path("locale/en/LC_MESSAGES/django.po")
    mo = Path("locale/en/LC_MESSAGES/django.mo")
    catalog = parse_po(po.read_text(encoding="utf-8"))
    write_mo(catalog, mo)
    print(f"compiled {len(catalog)} strings -> {mo}")


if __name__ == "__main__":
    main()
