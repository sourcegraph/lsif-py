def make_ranges(definition):
    return (
        make_range(definition.line, definition.column),
        make_range(definition.line, definition.column + len(definition.name)),
    )


def make_range(line, column):
    return {
        'line': line,
        'character': column,
    }


def wrap_contents(contents):
    return {
        'contents': [contents],
    }
