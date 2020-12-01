from typing import List

from jedi import Script
from jedi.api.classes import Definition


class Name:
    """
    An object that represents a reference or definition of a
    variable in a particular source file.
    """

    def __init__(self, definition: Definition):
        self.definition = definition

    def __eq__(self, other):
        return self.definition == other.definition

    def __hash__(self):
        return self.definition.__hash__()

    def is_definition(self) -> bool:
        """
        Return true if this name is a definition or assignment.
        """
        return self.definition.is_definition()

    def definitions(self) -> List["Name"]:
        """
        Get a list of Name objects which define or assign this
        particular usage of a variable reference. Generally, this
        will only include one object. If this name is a definition,
        the list will include itself.
        """
        return [Name(a) for a in self.definition.goto() if a != self.definition]

    @property
    def line(self) -> int:
        return self.definition.line - 1

    @property
    def lo(self) -> int:
        return self.definition.column

    @property
    def hi(self) -> int:
        return self.definition.column + len(self.definition.name)

    @property
    def docstring(self) -> str:
        return self.definition.docstring(raw=True, fast=False)


def get_names(source: str, filename: str) -> List[Name]:
    """
    Retrieve a list of Name objects for the given source.
    """
    return [
        Name(d) for d in Script(source, path=filename).get_names(all_scopes=True, references=True)
    ]
