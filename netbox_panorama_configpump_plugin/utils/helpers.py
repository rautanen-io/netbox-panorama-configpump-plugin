"""Views for Connection model."""

from __future__ import annotations

import difflib

from django.urls import reverse
from lxml import etree

from netbox_panorama_configpump_plugin.connection.models import Connection


def get_return_url(instance: Connection) -> str:
    """Get the return URL after the operation."""
    return reverse(
        "plugins:netbox_panorama_configpump_plugin:connection",
        kwargs={"pk": instance.pk},
    )


# pylint: disable=c-extension-no-member
def normalize_xml(xml_string: str) -> tuple[str, bool]:
    """Normalize the XML string."""

    if not xml_string or not xml_string.strip():
        return "", False

    try:
        parser = etree.XMLParser(remove_blank_text=True)
        root = etree.XML(xml_string.encode(), parser)

        # Recursively set text and tail to None for empty elements to make
        # them self-closing
        def set_empty_elements_to_self_closing(element):
            if (element.text is None or element.text.strip() == "") and len(
                element
            ) == 0:
                element.text = None
                element.tail = None
            for child in element:
                set_empty_elements_to_self_closing(child)

        set_empty_elements_to_self_closing(root)

        return etree.tostring(root, pretty_print=True, encoding="unicode"), True
    except etree.XMLSyntaxError:
        return "", False


def calculate_diff(
    current_config: str,
    new_config: str,
    ignore_line_whitespace: bool = False,
) -> dict[str, int]:
    """Calculate the diff between the current and new configuration."""
    curr_norm, curr_norm_valid = normalize_xml(current_config)
    new_norm, new_norm_valid = normalize_xml(new_config)

    # If both configurations are empty, no diff
    if not curr_norm_valid and not new_norm_valid:
        return {"added": 0, "removed": 0, "changed": 0}

    # If one is empty and the other is not, treat as all added/removed
    if not curr_norm:
        new_lines = new_norm.splitlines() if new_norm else []
        return {"added": len(new_lines), "removed": 0, "changed": 0}
    if not new_norm:
        curr_lines = curr_norm.splitlines() if curr_norm else []
        return {"added": 0, "removed": len(curr_lines), "changed": 0}

    if ignore_line_whitespace:
        curr_lines = [ln.strip() for ln in curr_norm.splitlines()]
        new_lines = [ln.strip() for ln in new_norm.splitlines()]
    else:
        curr_lines = curr_norm.splitlines()
        new_lines = new_norm.splitlines()

    matcher = difflib.SequenceMatcher(None, curr_lines, new_lines)
    added = removed = changed = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "insert":
            added += j2 - j1
        elif tag == "delete":
            removed += i2 - i1
        elif tag == "replace":
            removed_lines = i2 - i1
            added_lines = j2 - j1

            common = min(removed_lines, added_lines)
            changed += common

            if added_lines > removed_lines:
                added += added_lines - removed_lines
            elif removed_lines > added_lines:
                removed += removed_lines - added_lines

    return {"added": added, "removed": removed, "changed": changed}
