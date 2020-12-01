import json
from typing import IO, Dict, List, Callable

# A map from vertex labels to the fields they support. Fields
# are ordered based on their positional argument construction.
VERTEX_FIELDS: Dict[str, List[str]] = {
    "$event": ["kind", "scope", "data"],
    "definitionResult": [],
    "document": ["languageId", "uri", "contents"],
    "hoverResult": ["result"],
    "metaData": ["version", "positionEncoding", "projectRoot"],
    "project": ["kind"],
    "range": ["start", "end"],
    "referenceResult": [],
    "resultSet": [],
}

# A map from edge labels to the fields they support. Fields
# are ordered based on their positional argument construction.
EDGE_FIELDS: Dict[str, List[str]] = {
    "contains": ["outV", "inVs"],
    "item": ["outV", "inVs", "document", "property"],
    "next": ["outV", "inV"],
    "textDocument/definition": ["outV", "inV"],
    "textDocument/hover": ["outV", "inV"],
    "textDocument/references": ["outV", "inV"],
}


def _get_emitter_emit_name(base_name: str) -> str:
    name = base_name.replace("$", "").replace("/", "_").lower()
    return f"emit_{name}"


def _make_emitter(type_name: str, name: str, fields: List[str]) -> Callable[[...], int]:
    def emitter(self, *args):
        return self.emit(type=type_name, label=name, **dict(zip(fields, args)))

    return emitter


class Emitter:
    """
    Emitter writes LSIF-dump data to the given writer. The location to
    which dump data is written depends on the given writer. There are
    convenience methods to generate unique vertex and edge identifiers
    and map positional arguments ot the correct names for the label
    type. The majority of the methods in this class definition are
    added dynamically via setattr (below).
    """

    def __init__(self, writer: "BaseWriter"):
        self.writer = writer
        self._lines = 0

        # Add an emit_ * method to the Emitter class for each vertex
        # and edge type described above. The values for each field is
        # supplied positionally and are optional.
        for type_name, field_map in [("vertex", VERTEX_FIELDS), ("edge", EDGE_FIELDS)]:
            for name, fields in field_map.items():
                setattr(self, _get_emitter_emit_name(name), _make_emitter(type_name, name, fields))

    def emit(self, **kwargs) -> int:
        """
        Create a vertex or a node with the given fields and append
        it to the Emitter's output buffer. Generate and return a
        unique identifier for this component.
        """
        node_id = self._lines + 1
        self._lines += 1
        self.writer.write({"id": node_id, **kwargs})
        return node_id


class BaseWriter:
    def write(self, data: Dict):
        raise NotImplementedError


class FileWriter(BaseWriter):
    """
    FileWriter writes LSIF-dump data to the given file.
    """

    def __init__(self, file: IO):
        self.file = file

    def write(self, data: Dict):
        self.file.write(json.dumps(data, separators=(",", ":")) + "\n")


class DBWriter(BaseWriter):
    """
    DBWriter writes LSIF-dump data into a SQLite database.
    """

    def write(self, data: Dict):
        # TODO(efritz) - implement
        super().write(data)
