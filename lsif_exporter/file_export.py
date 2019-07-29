import base64
import jedi
import os


class DefinitionMeta:
    """
    A bag of properties around a single source definition.
    This contains previously generated identifiers needed
    when later linking a name reference to its definition.
    """
    def __init__(self, range_id, result_set_id, contents):
        self.range_id = range_id
        self.result_set_id = result_set_id
        self.contents = contents
        self.reference_range_ids = set()


class FileExporter:
    """
    Analysis the definitions and uses in the given file and
    add an LSIF document to the emitter. As analysis is done
    on a per-file basis, this class holds the majority of the
    exporter logic.
    """
    def __init__(self, filename, emitter, project_id, verbose):
        self.filename = filename
        self.emitter = emitter
        self.project_id = project_id
        self.verbose = verbose
        self.definition_metas = {}

    def export(self):
        print('Analyzing file {}'.format(self.filename))

        with open(self.filename) as f:
            source = f.read()
        self.source_lines = source.split('\n')

        self.document_id = self.emitter.emit_document(
            'py',
            'file://{}'.format(os.path.abspath(self.filename)),
            base64.b64encode(source.encode('utf-8')).decode(),
        )

        self.definitions = jedi.names(
            source,
            path=self.filename,
            all_scopes=True,
            references=True,
        )

        for definition in self.definitions:
            if definition.is_definition():
                self._export_definition(definition)

            self._export_definition_uses(definition)

        for definition, meta in self.definition_metas.items():
            self._link_definition_uses(definition, meta)

        self._emit_contains()

    def _export_definition(self, definition):
        """
        Emit vertices and edges related directly to a definition
        or assignment of a variable. Create a definition meta object
        with the generated LSIF identifiers and make it queryable by
        the same definition object.
        """
        # Print progress
        self._debug_def(definition)

        contents = {
            'language': 'py',
            'value': extract_definition_text(self.source_lines, definition),
        }

        # Emit hover tooltip and link it to a result set so that we can
        # re-use the same node for hover tooltips on usages.
        hover_id = self.emitter.emit_hoverresult({'contents': [contents]})
        result_set_id = self.emitter.emit_resultset()
        self.emitter.emit_textdocument_hover(result_set_id, hover_id)

        # Link result set to range
        range_id = self.emitter.emit_range(*make_ranges(definition))
        self.emitter.emit_next(range_id, result_set_id)

        # Stash the identifiers generated above so we can use then
        # when exporting related uses.
        self.definition_metas[definition] = DefinitionMeta(
            range_id,
            result_set_id,
            contents,
        )

    def _export_definition_uses(self, definition):
        """
        Emit vertices and edges related to any use of a definition.
        The definition must have already been exported by the above
        procedure.
        """
        try:
            assignments = definition.goto_assignments()
        except Exception:
            # TODO(efritz) - diagnose, document
            print('OH WEIRD')
            return

        for assignment in assignments:
            self._export_use(definition, assignment)

    def _export_use(self, definition, assignment):
        """
        Emit vertices and edges directly related to a single use of
        a definition.
        """
        meta = self.definition_metas.get(assignment)
        if not meta:
            # TODO(efritz) - what can we do here?
            return

        # Print progress
        self._debug_use(definition, assignment)

        if definition.is_definition():
            # The definition of the reference is the definition tiself.
            # It is against spec to have overlapping or duplicate ranges
            # in a single document, so we re-use the one that we had
            # generated previously.
            range_id = meta.range_id
        else:
            # This must be a unique name, generate a new range vertex
            range_id = self.emitter.emit_range(*make_ranges(definition))

        # Link use range to definition resultset
        self.emitter.emit_next(range_id, meta.result_set_id)
        result_id = self.emitter.emit_definitionresult()
        self.emitter.emit_textdocument_definition(meta.result_set_id, result_id)
        self.emitter.emit_item(result_id, [meta.range_id], self.document_id)

        # Add hover tooltip to use
        hover_id = self.emitter.emit_hoverresult({'contents': [meta.contents]})
        self.emitter.emit_textdocument_hover(meta.result_set_id, hover_id)

        # Bookkeep this reference for the link procedure below
        meta.reference_range_ids.add(range_id)

    def _link_definition_uses(self, definition, meta):
        """
        Emit vertices and edges related to the relationship between a definition
        and it use(s).
        """
        if len(meta.reference_range_ids) == 0:
            return

        result_id = self.emitter.emit_referenceresult()
        self.emitter.emit_textdocument_references(meta.result_set_id, result_id)
        self.emitter.emit_item(
            result_id,
            [meta.range_id],
            self.document_id,
            'definitions',
        )

        self.emitter.emit_item(
            result_id,
            sorted(list(meta.reference_range_ids)),
            self.document_id,
            'references',
        )

    def _emit_contains(self):
        """
        Emit vertices and edges related to parentage relationship. Currently
        this links only range vertices to its containing document vertex.
        """
        all_range_ids = set()
        for meta in self.definition_metas.values():
            all_range_ids.add(meta.range_id)
            all_range_ids.update(meta.reference_range_ids)

        # Deduplicate (and sort for better testing)
        all_range_ids = sorted(list(all_range_ids))

        # Link document to project
        self.emitter.emit_contains(self.project_id, [self.document_id])

        if all_range_ids:
            # Link ranges to document
            self.emitter.emit_contains(self.document_id, all_range_ids)

    #
    # Debugging Methods

    def _debug_def(self, definition):
        if not self.verbose:
            return

        print('\tFound definition: (line {}) {}'.format(
            definition.line,
            highlight_range(self.source_lines, definition).strip()),
        )

    def _debug_use(self, definition, assignment):
        if not self.verbose:
            return

        if assignment == definition:
            assignment_summary = 'assigned by self'
        else:
            assignment_summary = 'assigned at (line {}) {}'.format(
                assignment.line,
                highlight_range(self.source_lines, assignment),
            )

        print('\tFound reference: (line {}) {} {}'.format(
            definition.line,
            highlight_range(self.source_lines, definition),
            assignment_summary,
        ))


def make_ranges(definition):
    """
    Return a start and end range values for a range vertex.
    """
    lo = definition.column
    hi = definition.column + len(definition.name)

    return (
        {'line': definition.line - 1, 'character': lo},
        {'line': definition.line - 1, 'character': hi},
    )


def extract_definition_text(source_lines, definition):
    """
    Extract the text at the range described by the given definition.
    """
    lo = definition.column
    hi = definition.column + len(definition.name)
    line = source_lines[definition.line - 1]

    # TODO(efritz) - capture comments
    return line[lo:hi].rstrip()


def highlight_range(source_lines, definition):
    """
    Return the source line where the definition occurs with the
    range described by the definition highlighted with an ANSI code.
    """
    lo = definition.column
    hi = definition.column + len(definition.name)
    line = source_lines[definition.line - 1]

    return '{}\033[4;31m{}\033[0m{}'.format(
        line[:lo].lstrip(),
        line[lo:hi],
        line[hi:].rstrip(),
    )

