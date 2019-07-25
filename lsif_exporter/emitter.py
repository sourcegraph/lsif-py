import json

VERTEX_FIELD_MAP = {
    'definitionResult': [],
    'document': ['uri', 'languageId', 'contents'],
    'hoverResult': ['result'],
    'metaData': ['version', 'projectRoot', 'positionEncoding'],
    'project': ['kind'],
    'range': ['start', 'end'],
    'referenceResult': [],
    'resultSet': [],
}

EDGE_FIELD_MAP = {
    'contains': ['outV', 'inVs'],
    'item': ['outV', 'inVs', 'document', 'property'],
    'next': ['outV', 'inV'],
    'textDocument/definition': ['outV', 'inV'],
    'textDocument/hover': ['outV', 'inV'],
    'textDocument/references': ['outV', 'inV'],
}


class Emitter:
    def __init__(self):
        self._lines = []

    def print(self):
        for line in self._lines:
            print(json.dumps(line))

    def emit(self, **kwargs):
        node_id = self._next_id
        self._lines.append({'id': node_id, **kwargs})
        return node_id

    @property
    def _next_id(self):
        return str(len(self._lines) + 1)


def add_emitters():
    pairs = [
        ('vertex', VERTEX_FIELD_MAP),
        ('edge', EDGE_FIELD_MAP),
    ]

    for type_name, field_map in pairs:
        for name, fields in field_map.items():
            setattr(
                Emitter,
                'emit_{}'.format(name.split('/')[-1].lower()),
                make_emitter(type_name, name, fields),
            )


def make_emitter(type_name, name, fields):
    def emitter(self, *args):
        return self.emit(
            type=type_name,
            label=name,
            **dict(zip(fields, args)),
        )

    return emitter


add_emitters()
