import jedi


class Name:
    """
    An object that represents a reference or definition of a
    variable in a particular source file.
    """
    def __init__(self, definition):
        self.definition = definition

    def is_definition(self):
        """
        Return true if this name is a definition or assignment.
        """
        return self.definition.is_definition()

    def definitions(self):
        """
        Get a list of Name objects which define or assign this
        particular usage of a variable reference. Generally, this
        will only include one object. If this name is a definition,
        the list will include itself.
        """
        return [Name(a) for a in self.definition.goto_assignments() if a != self.definition]

    @property
    def line(self):
        return self.definition.line - 1

    @property
    def lo(self):
        return self.definition.column

    @property
    def hi(self):
        return self.definition.column + len(self.definition.name)

    @property
    def docstring(self):
        return self.definition.docstring(raw=True, fast=False)

    def __eq__(self, other):
        return self.definition == other.definition

    def __hash__(self):
        return self.definition.__hash__()


def get_names(source, filename):
    """
    Retrieve a list of Name objects for the given source.
    """
    definitions = jedi.names(
        source,
        path=filename,
        all_scopes=True,
        references=True,
    )

    return [Name(d) for d in definitions]
