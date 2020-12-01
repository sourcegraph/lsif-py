from enum import Enum
import json
from typing import IO, Dict


class EmitterNode(Enum):
    vertex = "vertex"
    edge = "edge"


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

    def emit(self, *, type: EmitterNode, label: str, **kwargs) -> int:
        """
        Create a vertex or a node with the given fields and append
        it to the Emitter's output buffer. Generate and return a
        unique identifier for this component.
        """
        node_id = self._lines + 1
        self._lines += 1
        self.writer.write({"id": node_id, "type": type.value, "label": label, **kwargs})
        return node_id

    # Vertex Emits

    def emit_event(self, kind, scope, data) -> int:
        return self.emit(type=EmitterNode.vertex, label="event", kind=kind, scope=scope, data=data)

    def emit_definition_result(self) -> int:
        return self.emit(type=EmitterNode.vertex, label="definitionResult")

    def emit_document(self, language_id, uri, contents) -> int:
        return self.emit(
            type=EmitterNode.vertex,
            label="document",
            languageId=language_id,
            uri=uri,
            contents=contents,
        )

    def emit_hover_result(self, result) -> int:
        return self.emit(type=EmitterNode.vertex, label="hoverResult", result=result)

    def emit_metadata(self, version, position_encoding, project_root) -> int:
        return self.emit(
            type=EmitterNode.vertex,
            label="metaData",
            version=version,
            positionEncoding=position_encoding,
            projectRoot=project_root,
        )

    def emit_project(self, kind) -> int:
        return self.emit(type=EmitterNode.vertex, label="project", kind=kind)

    def emit_range(self, start, end) -> int:
        return self.emit(type=EmitterNode.vertex, label="range", start=start, end=end)

    def emit_reference_result(self) -> int:
        return self.emit(type=EmitterNode.vertex, label="referenceResult")

    def emit_result_set(self) -> int:
        return self.emit(type=EmitterNode.vertex, label="resultSet")

    # Edge Emits

    def emit_contains(self, out_v, in_vs) -> int:
        return self.emit(type=EmitterNode.edge, label="contains", outV=out_v, inVs=in_vs)

    def emit_item(self, out_v, in_vs, document, property) -> int:
        return self.emit(
            type=EmitterNode.edge,
            label="contains",
            outV=out_v,
            inVs=in_vs,
            document=document,
            property=property,
        )

    def emit_next(self, out_v, in_v) -> int:
        return self.emit(type=EmitterNode.edge, label="contains", outV=out_v, inV=in_v)

    def emit_text_document_definition(self, out_v, in_v) -> int:
        return self.emit(
            type=EmitterNode.edge, label="textDocument/definition", outV=out_v, inV=in_v
        )

    def emit_text_document_hover(self, out_v, in_v) -> int:
        return self.emit(type=EmitterNode.edge, label="textDocument/hover", outV=out_v, inV=in_v)

    def emit_text_document_references(self, out_v, in_v) -> int:
        return self.emit(
            type=EmitterNode.edge, label="textDocument/references", outV=out_v, inV=in_v
        )


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
