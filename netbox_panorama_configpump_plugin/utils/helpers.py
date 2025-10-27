"""Views for Connection model."""

from __future__ import annotations

import difflib
import re
import xml.etree.ElementTree as ET
from typing import Any

from django.conf import settings
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


def sanitize_error_message(msg: str) -> str:
    """
    Sanitize sensitive information from error messages.
    """
    sanitized = msg

    plugin_config = getattr(settings, "PLUGINS_CONFIG", {}).get(
        "netbox_panorama_configpump_plugin", {}
    )
    tokens = plugin_config.get("tokens", {}) or {}

    for token_value in tokens.values():
        if token_value and isinstance(token_value, str) and token_value in sanitized:
            sanitized = sanitized.replace(token_value, "***")

    sanitized = re.sub(r"0x[0-9a-fA-F]+", "0x***", sanitized)
    sanitized = re.sub(r"key=[^&\s]+", "key=***", sanitized)

    return sanitized


def sanitize_nested_values(value: Any) -> Any:
    """
    Recursively sanitize nested structures using sanitize_error_message for strings.
    """
    if isinstance(value, dict):
        return {k: sanitize_nested_values(v) for k, v in value.items()}
    if isinstance(value, list):
        return [sanitize_nested_values(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_nested_values(item) for item in value)
    if isinstance(value, str):
        return sanitize_error_message(value)
    return value


def _parse_xml_with_validation(xml_str: str) -> etree._Element:
    """
    First checks that the XML is valid using ElementTree, then parses it again with
    lxml so XPath works.
    """

    try:
        ET.fromstring(xml_str)
    except (ET.ParseError, AttributeError, KeyError) as exc:
        raise ValueError(f"Error parsing config: {exc}") from exc

    try:
        return etree.fromstring(xml_str.encode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Error parsing config with lxml: {exc}") from exc


def _normalize_xpaths(xpaths: list[str]) -> list[str]:
    """
    Cleans up the XPath expressions by removing trailing slashes, except for the root /.
    """

    return [xp.rstrip("/") if xp != "/" else xp for xp in xpaths]


def _is_whole_document_requested(xpaths: list[str], root_tag: str) -> bool:
    """
    Checks whether the XPath list is asking for the entire document, e.g. / or /config.
    """

    return any(xp in ("/", f"/{root_tag}") for xp in xpaths)


def _safe_xpath(node, xp: str):
    """
    Executes the XPath search, but catches errors and rethrows them as nice error
    messages.
    """
    try:
        return node.xpath(xp)
    except Exception as exc:
        raise ValueError(f"Invalid XPath '{xp}': {exc}") from exc


def _shallow_clone(node: etree._Element) -> etree._Element:
    """
    Creates a copy of an XML tag without its children, only with the attributes.
    """

    return etree.Element(node.tag, **{k: v for k, v in node.attrib.items()})


def _find_child(parent: etree._Element, node: etree._Element):
    """
    Checks if parent already has a child with the same tag name and attributes as node.
    """

    for child in parent:
        if child.tag == node.tag and dict(child.attrib) == dict(node.attrib):
            return child
    return None


def _ensure_ancestor_chain(
    new_root: etree._Element,
    match: etree._Element,
    source_root: etree._Element,
):
    """
    Recreates the path of parent nodes (ancestors) above the match, so that the new
    output keeps the original structure.
    """

    ancestors = list(match.iterancestors())[::-1]
    cursor = new_root

    for ancestor in ancestors:
        if ancestor is source_root:
            continue

        existing = _find_child(cursor, ancestor)
        if existing is None:
            existing = _shallow_clone(ancestor)
            cursor.append(existing)
        cursor = existing

    return cursor


# pylint: disable=c-extension-no-member
def extract_matching_xml_by_xpaths(xml_str: str, xpath_entries: list[str]) -> str:
    """
    Takes an XML document and a list of XPath filters, and returns a new XML document
    that only contains the elements that matched those filters — including their parent
    paths so the structure stays valid.
    """

    if not xml_str or not xpath_entries:
        return ""

    source_root = _parse_xml_with_validation(xml_str)
    expanded = _normalize_xpaths(xpath_entries)

    if _is_whole_document_requested(expanded, source_root.tag):
        return etree.tostring(source_root, pretty_print=True, encoding="unicode")

    new_root = _shallow_clone(source_root)

    for xp in expanded:
        for match in _safe_xpath(source_root, xp):
            if not hasattr(match, "tag"):
                continue
            cursor = _ensure_ancestor_chain(new_root, match, source_root)
            if _find_child(cursor, match) is None:
                cursor.append(etree.fromstring(etree.tostring(match)))

    return etree.tostring(
        new_root,
        pretty_print=True,
        encoding="unicode",
        # doctype='<?xml version="1.0" encoding="utf-8"?>',
    )


def list_item_names_in_xml(configuration: str, item_type: str) -> list[str]:
    """
    Process the configuration string and extract item names from the XML structure.

    Looks for items in the path:
    <config><devices><entry><{item_type}><entry name="ITEM_NAME">

    Args:
        configuration: XML configuration string
        item_type: Type of items to extract ("template" or "device-group")

    Returns:
        List of item names found in the configuration
    """
    try:
        root = ET.fromstring(configuration)

        item_list = []

        devices = root.find("devices")
        if devices is not None:
            for device_entry in devices.findall("entry"):
                item_section = device_entry.find(item_type)
                if item_section is not None:
                    # Find all item entries within this device
                    for item_entry in item_section.findall("entry"):
                        item_name = item_entry.get("name")
                        if item_name:
                            item_list.append(item_name)

        return item_list

    except ET.ParseError as e:
        raise ValueError(f"Error parsing XML config: {e}") from e
    except (AttributeError, KeyError) as e:
        raise ValueError(f"Error processing config: {e}") from e


def extract_strings_from_nested(value: Any) -> str:
    """
    Recursively extract all string values from nested dictionaries and lists.

    Handles structures like:
    - {'msg': {'line': {'msg': {'line': 'Config loaded from nb-test_device_b.xml'}}}}
    - ['msg1', 'msg2']
    - {'msg': 'simple'}
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join([extract_strings_from_nested(item) for item in value])
    if isinstance(value, dict):
        # Extract all string values from the dict recursively
        string_values = []
        for v in value.values():
            extracted = extract_strings_from_nested(v)
            if extracted:
                string_values.append(extracted)
        return " ".join(string_values)
    return ""
