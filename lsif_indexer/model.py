"""Define the LSIF protocol as a Pydantic model.

Classes in this module map to kinds of LSIF data, each can be output by calling
.json(), ids and labels are automatically generated for you, and only the
fields unique to each class are required in their constructors.
"""

from itertools import count
from typing import Literal, Union

from pydantic import BaseModel, Field

import stringcase

counter = count(start=1)


class Referent(BaseModel):

    id: int = Field(default_factory=lambda: next(counter))

    def json(
        self,
        *,
        by_alias=True,
        separators=(",", ":"),
        **kwargs,
    ) -> str:
        return super().json(
            by_alias=by_alias,
            separators=separators,
            **kwargs,
        )

    class Config:
        allow_population_by_field_name = True
        alias_generator = stringcase.camelcase


class LSIFEntry(Referent):

    ty: Literal["edge", "vertex"]
    label: str

    class Config:
        fields = {"ty": "type"}


class Vertex(LSIFEntry):

    ty: Literal["vertex"] = "vertex"


class Edge(LSIFEntry):

    ty: Literal["edge"] = "edge"


class Position(BaseModel):
    line: int
    character: int


class Range(Vertex):
    label = "range"
    start: Position
    end: Position


class Next(Edge):
    label = "next"
    out_v: int
    in_v: int


class Contains(Edge):
    label = "contains"
    out_v: int
    in_vs: list[int]


class MetaData(Vertex):
    class ToolInfo(BaseModel):
        name: str

    label = "metaData"
    version: str = "0.4.3"
    position_encoding: str = "utf-16"
    project_root: str  # AnyUrl
    tool_info: ToolInfo


class Project(Vertex):
    label = "project"
    kind: str = "py"


class Document(Vertex):
    label = "document"
    language_id: str
    uri: str
    contents: str


class ResultSet(Vertex):
    label = "resultSet"


class Snippet(BaseModel):
    language: str
    value: str


HoverResultContent = Union[Snippet, str]


class HoverResultContents(BaseModel):
    contents: list[HoverResultContent]


class HoverResult(Vertex):
    label = "hoverResult"
    result: HoverResultContents


class Hover(Edge):
    label = "textDocument/hover"
    out_v: int
    in_v: int


class DefinitionResult(Vertex):
    label = "definitionResult"


class Definition(Edge):
    label = "textDocument/definition"
    out_v: int
    in_v: int


class ReferenceResult(Vertex):
    label = "referenceResult"


class Reference(Edge):
    label = "textDocument/references"
    out_v: int
    in_v: int


class Event(Vertex):
    label = "$event"
    kind: str
    scope: Literal["project", "document"]
    data: int


class Begin(Event):
    kind = "begin"


class End(Event):
    kind = "end"


class Item(Edge):
    label = "item"
    out_v: int
    in_vs: list[int]
    document: int
    property: str
