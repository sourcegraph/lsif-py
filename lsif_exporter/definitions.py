import jedi


def get_definitions(source, filename):
    definitions = jedi.names(
        source,
        path=filename,
        all_scopes=True,
        references=True,
    )

    return sorted(definitions, key=lambda d: d.line)
