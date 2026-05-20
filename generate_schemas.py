#!/usr/bin/env python3
"""
Generates the components/schemas section of openapi.yml from schema.xsd.

Usage:
    python3 generate_schemas.py           # prints YAML to stdout
    python3 generate_schemas.py --update  # patches components/schemas in openapi.yml in-place

The generated schemas cover every top-level XSD element.  Mixed-content
elements (text + optional attributes) are rendered as plain `type: string`
when they have no attributes, or as an object with a `_text` field plus
attribute properties when they do carry attributes.
"""

import sys
import re
import textwrap
import xmlschema
from xmlschema import XsdElement, XsdAttribute

EVENTOR_EXTENSIONS_NS = "http://eventor.orientering.se/iofxmlextensions"

# Hand-written schemas for Eventor-specific elements that appear inside
# `<Extensions>` in IOF XML 3.0 responses. These are not part of the IOF XSD
# (which lives at https://github.com/international-orienteering-federation/datastandard-v3)
# so they are documented here. Appended to the generated schemas block so they
# survive regeneration from schema.xsd.
EXTRA_SCHEMAS_YAML = """\
    EventorEventRaceId:
      type: object
      description: Eventor's internal ID for a race within an event. Appears inside `<Extensions>` on `Race` elements in IOF XML responses.
      properties:
        _text:
          type: integer
          description: The race ID.
        type:
          type: string
          example: Eventor
          xml:
            attribute: true
      required:
        - type
      xml:
        name: EventRaceId
        namespace: http://eventor.orientering.se/iofxmlextensions
        prefix: eventor
    EventorStartListExists:
      type: boolean
      description: Whether a start list has been published for the parent event or race.
      xml:
        name: StartListExists
        namespace: http://eventor.orientering.se/iofxmlextensions
        prefix: eventor
    EventorResultListExists:
      type: boolean
      description: Whether a result list has been published for the parent event or race.
      xml:
        name: ResultListExists
        namespace: http://eventor.orientering.se/iofxmlextensions
        prefix: eventor
    EventorDiscipline:
      type: string
      description: |
        Eventor's discipline classification for the event or race.
        May appear multiple times on the same parent — the value set lists every
        discipline the event/race accommodates.
      enum:
        - Foot
        - MountainBike
        - Ski
        - Trail
        - Indoor
      xml:
        name: Discipline
        namespace: http://eventor.orientering.se/iofxmlextensions
        prefix: eventor
    EventorLightCondition:
      type: string
      description: Light condition for the race.
      enum:
        - Day
        - Night
        - DayAndNight
      xml:
        name: LightCondition
        namespace: http://eventor.orientering.se/iofxmlextensions
        prefix: eventor
    EventorAttribute:
      type: object
      description: |
        A custom event attribute defined by the Eventor instance. The set of
        attributes is instance-specific — e.g. the Norwegian Eventor exposes
        attributes like `Flexoløp`, `Ukas løype` and `Paratilbud`.
      properties:
        _text:
          type: string
          description: Human-readable attribute name.
          example: Ukas løype
        id:
          type: integer
          example: 2
          xml:
            attribute: true
      required:
        - id
      xml:
        name: Attribute
        namespace: http://eventor.orientering.se/iofxmlextensions
        prefix: eventor
    EventorExtensions:
      type: object
      description: |
        Container for Eventor-specific elements that appear inside `<Extensions>`
        in IOF XML 3.0 responses. All children use the namespace
        `http://eventor.orientering.se/iofxmlextensions` (prefix `eventor:`).

        Which children appear depends on the parent IOF element:

        - On `Event`: `StartListExists`, `ResultListExists`, zero or more
          `Discipline`, zero or more `Attribute`.
        - On `Race`: `EventRaceId`, `StartListExists`, `ResultListExists`,
          zero or more `Discipline`, `LightCondition`.

        `Discipline` is repeatable — an event/race that allows multiple
        disciplines lists each one as a separate element.

        These extensions are not part of the public IOF XSD — see the IOF
        datastandard repository for the IOF-defined part of the response:
        https://github.com/international-orienteering-federation/datastandard-v3
      properties:
        EventRaceId:
          $ref: '#/components/schemas/EventorEventRaceId'
        StartListExists:
          $ref: '#/components/schemas/EventorStartListExists'
        ResultListExists:
          $ref: '#/components/schemas/EventorResultListExists'
        Discipline:
          type: array
          items:
            $ref: '#/components/schemas/EventorDiscipline'
          xml:
            name: Discipline
            namespace: http://eventor.orientering.se/iofxmlextensions
            prefix: eventor
            wrapped: false
        LightCondition:
          $ref: '#/components/schemas/EventorLightCondition'
        Attribute:
          type: array
          items:
            $ref: '#/components/schemas/EventorAttribute'
          xml:
            name: Attribute
            namespace: http://eventor.orientering.se/iofxmlextensions
            prefix: eventor
            wrapped: false
      xml:
        name: Extensions
"""

XSD_TO_OPENAPI_TYPE = {
    "string":       ("string",  None),
    "integer":      ("integer", None),
    "int":          ("integer", None),
    "long":         ("integer", "int64"),
    "double":       ("number",  "double"),
    "decimal":      ("number",  None),
    "float":        ("number",  "float"),
    "boolean":      ("boolean", None),
    "date":         ("string",  "date"),
    "dateTime":     ("string",  "date-time"),
    "base64Binary": ("string",  "byte"),
    "anySimpleType":("string",  None),
    "anyURI":       ("string",  "uri"),
    "NMTOKEN":      ("string",  None),
}


def xsd_type_to_openapi(type_obj):
    """Return (oa_type, oa_format, enum_list) for an XSD type."""
    if type_obj is None:
        return "string", None, None
    name = type_obj.local_name if type_obj.local_name else ""
    base = XSD_TO_OPENAPI_TYPE.get(name, ("string", None))
    enums = None
    if hasattr(type_obj, "enumeration") and type_obj.enumeration:
        enums = list(type_obj.enumeration)
    return base[0], base[1], enums


def attr_schema(attr: XsdAttribute) -> dict:
    """Build an OpenAPI property dict for a single XSD attribute."""
    oa_type, oa_format, enums = xsd_type_to_openapi(attr.type)
    prop = {"type": oa_type}
    if oa_format:
        prop["format"] = oa_format
    if enums:
        prop["enum"] = enums
    if attr.use != "required" and hasattr(attr, "default") and attr.default is not None:
        prop["default"] = attr.default
    prop["xml"] = {"attribute": True}
    return prop


def element_schema(el: XsdElement, schema: xmlschema.XMLSchema,
                   visited=None) -> dict:
    """
    Recursively build an OpenAPI schema dict for an XSD element.

    visited prevents infinite recursion for self-referencing types
    (e.g. Organisation -> ParentOrganisation -> Organisation).
    """
    if visited is None:
        visited = set()

    t = el.type

    # ── Simple / atomic type (xs:string, xs:integer, …) ──────────────────────
    if t.is_simple():
        oa_type, oa_format, enums = xsd_type_to_openapi(t)
        prop: dict = {"type": oa_type}
        if oa_format:
            prop["format"] = oa_format
        if enums:
            prop["enum"] = enums
        return prop

    # ── Mixed-content complex type (text content + optional attrs) ───────────
    if t.mixed:
        attrs = dict(t.attributes)
        if not attrs:
            # Pure text container, no attributes
            return {"type": "string"}
        # Text + attributes  →  object with _text + attribute properties
        props: dict = {"_text": {"type": "string"}}
        required = []
        for aname, attr in attrs.items():
            props[aname] = attr_schema(attr)
            if attr.use == "required":
                required.append(aname)
        out: dict = {"type": "object", "properties": props}
        if required:
            out["required"] = required
        return out

    # ── Complex type with children ───────────────────────────────────────────
    type_key = id(t)
    if type_key in visited:
        # Break recursion — emit a $ref to the element name if it is top-level
        elem_name = el.local_name
        if elem_name in schema.elements:
            return {"$ref": f"#/components/schemas/{elem_name}"}
        return {"type": "object"}

    visited = visited | {type_key}

    properties: dict = {}
    required_props: list = []
    array_item_names: set = set()  # track names already added as arrays

    # Children (sequence / choice elements)
    try:
        children = list(t.content) if hasattr(t, "content") and t.content is not None else []
    except TypeError:
        children = []
    for child in children:
        if not isinstance(child, XsdElement):
            continue
        if child.name is None:
            continue
        cname = child.local_name
        is_array = child.max_occurs is None or child.max_occurs > 1

        if is_array and cname in array_item_names:
            continue  # already added

        # If child element is a top-level schema element, use $ref
        if cname in schema.elements and cname != el.local_name:
            item_schema: dict = {"$ref": f"#/components/schemas/{cname}"}
        else:
            item_schema = element_schema(child, schema, visited)

        if is_array:
            array_item_names.add(cname)
            prop = {
                "type": "array",
                "items": item_schema,
                "xml": {"name": cname, "wrapped": False},
            }
        else:
            prop = item_schema

        properties[cname] = prop

        if child.min_occurs and child.min_occurs > 0 and not is_array:
            required_props.append(cname)

    # XML attributes
    for aname, attr in t.attributes.items():
        properties[aname] = attr_schema(attr)
        if attr.use == "required":
            required_props.append(aname)

    out = {"type": "object"}
    if properties:
        out["properties"] = properties
    if required_props:
        out["required"] = sorted(set(required_props))
    return out


def quote_str(s: str) -> str:
    """Single-quote a YAML string value if it needs quoting."""
    if re.search(r"[:{}\[\],#&*?|<>=!%@`]", s) or s in ("true", "false", "null", "~"):
        return f"'{s}'"
    return s


def to_yaml(obj, indent: int = 0) -> str:
    """Minimal YAML serialiser (handles dict / list / str / int / bool / None)."""
    pad = "  " * indent
    if isinstance(obj, dict):
        if not obj:
            return "{}"
        lines = []
        for k, v in obj.items():
            key = quote_str(str(k))
            rendered = to_yaml(v, indent + 1)
            if rendered.startswith("\n"):
                lines.append(f"{pad}{key}:{rendered}")
            elif isinstance(v, (dict, list)) and v:
                lines.append(f"{pad}{key}:\n{rendered}")
            else:
                lines.append(f"{pad}{key}: {rendered}")
        return "\n".join(lines)
    elif isinstance(obj, list):
        if not obj:
            return "[]"
        lines = []
        for item in obj:
            rendered = to_yaml(item, indent + 1)
            first_line, *rest = rendered.split("\n")
            lines.append(f"{pad}- {first_line.lstrip()}")
            for r in rest:
                lines.append(f"{pad}  {r.lstrip()}")
        return "\n".join(lines)
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    elif obj is None:
        return "null"
    elif isinstance(obj, str):
        return quote_str(obj)
    else:
        return str(obj)


def generate_schemas(xsd_path: str = "schema.xsd") -> str:
    schema = xmlschema.XMLSchema(xsd_path)

    lines = ["  schemas:"]
    for name, el in sorted(schema.elements.items()):
        s = element_schema(el, schema)
        s["xml"] = {"name": name}
        yaml_body = to_yaml(s, indent=3)
        lines.append(f"    {name}:")
        lines.append(yaml_body)

    lines.append(EXTRA_SCHEMAS_YAML.rstrip("\n"))
    return "\n".join(lines)


def update_openapi(schemas_yaml: str, openapi_path: str = "openapi.yml"):
    with open(openapi_path) as f:
        content = f.read()

    # Replace the existing components/schemas block (or insert after securitySchemes)
    schemas_block = schemas_yaml + "\n"

    # Match existing schemas block
    pattern = re.compile(
        r"^  schemas:\n.*?(?=^\S|\Z)", re.MULTILINE | re.DOTALL
    )
    if pattern.search(content):
        new_content = pattern.sub(schemas_block, content)
    else:
        # Insert after securitySchemes block
        new_content = re.sub(
            r"(  securitySchemes:.*?\n)(\S)",
            lambda m: m.group(1) + schemas_block + m.group(2),
            content,
            flags=re.DOTALL,
        )

    with open(openapi_path, "w") as f:
        f.write(new_content)
    print(f"Updated {openapi_path}", file=sys.stderr)


if __name__ == "__main__":
    schemas_yaml = generate_schemas("schema.xsd")
    if "--update" in sys.argv:
        update_openapi(schemas_yaml)
    else:
        print(schemas_yaml)
