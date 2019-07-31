import json


class Emitter:
    """
    Emitter writes LSIF-dump data to the given writer. The location to
    which dump data is written depends on the given writer. There are
    convenience methods to generate unique vertex and edge identifiers
    and map positional arguments ot the correct names for the label
    type. The majority of the methods in this class definition are
    added dynamically via setattr (below).
    """
    def __init__(self, writer):
        self.writer = writer
        self._lines = 0

    def emit(self, **kwargs):
        """
        Create a vertex or a node with the given fields and append
        it to the Emitter's output buffer. Generate and return a
        unique identifier for this component.
        """
        node_id = self._lines + 1
        self._lines += 1
        self.writer.write({'id': node_id, **kwargs})
        return node_id


class FileWriter:
    """
    FileWriter writes LSIF-dump data to the given file.
    """
    def __init__(self, file):
        self.file = file

    def write(self, data):
        self.file.write(json.dumps(data, separators=(',', ':')) + '\n')


class DBWriter:
    """
    DBWriter writes LSIF-dump data into a SQLite database.
    """
    def __init__(self):
        pass

    def write(self, data):
        # TODO(efritz) - implement
        raise RuntimeError('Unimplemented')


# A map from vertex labels to the fields they support. Fields
# are ordered based on their positional argument construction.
VERTEX_FIELDS = {
    '$event': ['kind', 'scope', 'data'],
    'definitionResult': [],
    'document': ['languageId', 'uri', 'contents'],
    'hoverResult': ['result'],
    'metaData': ['version', 'positionEncoding', 'projectRoot'],
    'project': ['kind'],
    'range': ['start', 'end'],
    'referenceResult': [],
    'resultSet': [],
}

# A map from edge labels to the fields they support. Fields
# are ordered based on their positional argument construction.
EDGE_FIELDS = {
    'contains': ['outV', 'inVs'],
    'item': ['outV', 'inVs', 'document', 'property'],
    'next': ['outV', 'inV'],
    'textDocument/definition': ['outV', 'inV'],
    'textDocument/hover': ['outV', 'inV'],
    'textDocument/references': ['outV', 'inV'],
}


def add_emitters():
    """
    Add an emit_* method to the Emitter class for each vertex and
    edge type described above. The values for each field is supplied
    positionally and are optional.
    """
    def make_emitter(type_name, name, fields):
        def emitter(self, *args):
            return self.emit(
                type=type_name,
                label=name,
                **dict(zip(fields, args)),
            )

        return emitter

    for type_name, field_map in [('vertex', VERTEX_FIELDS), ('edge', EDGE_FIELDS)]:
        for name, fields in field_map.items():
            setattr(
                Emitter,
                'emit_{}'.format(name.replace('$', '').replace('/', '_').lower()),
                make_emitter(type_name, name, fields),
            )


# Meta-construct the Emitter class
add_emitters()
