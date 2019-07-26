def definition_summary(source_lines, definition):
    lo = definition.column
    hi = definition.column + len(definition.name)
    line = source_lines[definition.line - 1]

    try:
        # TODO(efritz) - capture comments
        return line[lo:hi].rstrip()
    except IndexError:
        # TODO(Efritz) - shouldn't need this guard
        return line


def highlight_range(source_lines, definition):
    lo = definition.column
    hi = definition.column + len(definition.name)
    line = source_lines[definition.line - 1]

    return '{}\033[4;31m{}\033[0m{}'.format(
        line[:lo],
        line[lo:hi],
        line[hi:].rstrip(),
    )


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
