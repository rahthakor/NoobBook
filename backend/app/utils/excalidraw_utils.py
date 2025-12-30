"""
Excalidraw Utilities - Convert simplified elements to Excalidraw format.

Used by wireframe_service for generating Excalidraw-compatible wireframes.
"""

import uuid
from typing import Dict, Any, List


def convert_to_excalidraw_elements(elements: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Convert simplified element format to full Excalidraw element format.

    Excalidraw elements require specific properties.
    We add defaults and generate unique IDs for each element.

    Args:
        elements: List of simplified element dicts from Claude

    Returns:
        List of Excalidraw-compatible element dicts
    """
    excalidraw_elements = []

    for elem in elements:
        element_id = str(uuid.uuid4())[:8]
        elem_type = elem.get("type", "rectangle")

        # Base element properties
        base = {
            "id": element_id,
            "type": elem_type,
            "x": elem.get("x", 0),
            "y": elem.get("y", 0),
            "strokeColor": elem.get("strokeColor", "#000000"),
            "backgroundColor": elem.get("backgroundColor", "transparent"),
            "fillStyle": elem.get("fillStyle", "hachure"),
            "strokeWidth": elem.get("strokeWidth", 1),
            "roughness": 1,  # Hand-drawn effect
            "opacity": 100,
            "seed": hash(element_id) % 1000000,  # Random seed for roughness
            "version": 1,
            "isDeleted": False,
            "groupIds": [],
            "boundElements": None,
            "locked": False,
        }

        if elem_type == "text":
            base.update(_build_text_properties(elem))
        elif elem_type in ["line", "arrow"]:
            base.update(_build_line_properties(elem, elem_type))
        else:
            # Rectangle, ellipse, diamond
            base.update({
                "width": elem.get("width", 100),
                "height": elem.get("height", 50),
            })

        excalidraw_elements.append(base)

        # If element has a label, add it as a separate text element
        label = elem.get("label")
        if label and elem_type in ["rectangle", "ellipse", "diamond"]:
            label_elem = _build_label_element(elem, label)
            excalidraw_elements.append(label_elem)

    return excalidraw_elements


def _build_text_properties(elem: Dict[str, Any]) -> Dict[str, Any]:
    """Build text-specific properties."""
    text_content = elem.get("text", "Text")
    font_size = elem.get("fontSize", 16)

    return {
        "text": text_content,
        "fontSize": font_size,
        "fontFamily": 1,  # Virgil (hand-drawn)
        "textAlign": "left",
        "verticalAlign": "top",
        "baseline": font_size,
        "width": len(text_content) * font_size * 0.6,
        "height": font_size * 1.2,
        "containerId": None,
        "originalText": text_content,
    }


def _build_line_properties(elem: Dict[str, Any], elem_type: str) -> Dict[str, Any]:
    """Build line/arrow-specific properties."""
    points = elem.get("points", [[0, 0], [100, 0]])

    return {
        "points": points,
        "lastCommittedPoint": points[-1] if points else [0, 0],
        "startBinding": None,
        "endBinding": None,
        "startArrowhead": None,
        "endArrowhead": "arrow" if elem_type == "arrow" else None,
    }


def _build_label_element(elem: Dict[str, Any], label: str) -> Dict[str, Any]:
    """Build a label text element for a shape."""
    label_id = str(uuid.uuid4())[:8]
    label_x = elem.get("x", 0) + elem.get("width", 100) / 2 - len(label) * 4
    label_y = elem.get("y", 0) + elem.get("height", 50) / 2 - 8

    return {
        "id": label_id,
        "type": "text",
        "x": label_x,
        "y": label_y,
        "text": label,
        "fontSize": 14,
        "fontFamily": 1,
        "textAlign": "center",
        "verticalAlign": "middle",
        "strokeColor": "#666666",
        "backgroundColor": "transparent",
        "fillStyle": "solid",
        "strokeWidth": 1,
        "roughness": 1,
        "opacity": 100,
        "seed": hash(label_id) % 1000000,
        "version": 1,
        "isDeleted": False,
        "groupIds": [],
        "boundElements": None,
        "locked": False,
        "width": len(label) * 8,
        "height": 18,
        "baseline": 14,
        "containerId": None,
        "originalText": label,
    }
