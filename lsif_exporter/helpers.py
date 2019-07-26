# TODO(efritz) - provide better context
def definition_summary(source_lines, definition):
    line = source_lines[definition.line - 1]

    try:
        return line[definition.column:definition.column + len(definition.name)]
    except IndexError:
        return line


def make_ranges(definition):
    return (
        make_range(definition.line, definition.column),
        make_range(definition.line, definition.column + len(definition.name)),
    )


def make_range(line, column):
    return {
        'line': line - 1,
        'character': column,
    }


def wrap_contents(contents):
    return {
        'contents': [contents],
    }
