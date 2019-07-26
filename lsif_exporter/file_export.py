import base64
import jedi
import os

from .helpers import (
    definition_summary,
    highlight_range,
    make_ranges,
    wrap_contents,
)


class FileExporter:
    def __init__(self, emitter, project_id):
        self.emitter = emitter
        self.project_id = project_id
        self.definition_metas = {}
        self.reference_range_ids = []

    def export(self, filename):
        print('File: {}'.format(filename))

        with open(filename) as f:
            source = f.read()

        self.source_lines = source.split('\n')
        self.definitions = get_definitions(source, filename)

        self.document_id = self.emitter.emit_document(
            'file://{}'.format(os.path.abspath(filename)),
            'py',
            hash_source(source),
        )

        self._export_defs()
        self._export_uses()

        self.emitter.emit_contains(self.project_id, [self.document_id])

        meta_set = self.definition_metas.values()
        definition_range_ids = map(lambda m: m.range_id, meta_set)
        all_range_ids = list(definition_range_ids) + self.reference_range_ids

        if all_range_ids:
            self.emitter.emit_contains(self.document_id, all_range_ids)

    def _export_defs(self):
        for definition in self.definitions:
            if not definition.is_definition():
                continue

            self._export_def_pre_use(definition)

    def _export_uses(self):
        for definition in self.definitions:
            for assignment in definition.goto_assignments():
                meta = self.definition_metas.get(assignment)
                if meta:
                    if assignment == definition:
                        assignment_summary = 'assigned by self'
                    else:
                        assignment_summary = 'assigned at (line {}) {}'.format(
                            assignment.line,
                            highlight_range(self.source_lines, assignment),
                        )

                    # TODO(efritz) - enable with verbose flag
                    print('\tFound reference: (line {}) {} {}'.format(
                        definition.line,
                        highlight_range(self.source_lines, definition),
                        assignment_summary,
                    ))

                    self._export_assignment(definition, meta, assignment)

    def _export_def_pre_use(self, definition):
        # TODO(efritz) - enable with verbose flag
        print('\tFound definition: (line {}) {}'.format(
            definition.line,
            highlight_range(self.source_lines, definition).strip()),
        )

        contents = {
            'language': 'py',
            'value': definition_summary(self.source_lines, definition),
        }

        result_set_id = self.emitter.emit_resultset()
        range_id = self.emitter.emit_range(*make_ranges(definition))
        hover_id = self.emitter.emit_hoverresult(wrap_contents(contents))

        self.emitter.emit_next(range_id, result_set_id)
        self.emitter.emit_textdocument_hover(result_set_id, hover_id)

        self.definition_metas[definition] = DefinitionMeta(
            range_id,
            result_set_id,
            contents,
        )

    def _export_def_post_use(self, definition, meta, reference_range_ids):
        result_id = self.emitter.emit_referenceresult()
        self.emitter.emit_textdocument_references(meta.result_set_id, result_id)
        self.emitter.emit_item(
            result_id,
            [meta.range_id],
            self.document_id,
            'definitions',
        )

        if len(reference_range_ids) > 0:
            self.emitter.emit_item(
                result_id,
                reference_range_ids,
                self.document_id,
                'references',
            )

    def _export_assignment(self, definition, meta, assignment):
        reference_range_ids = []
        reference_range_ids.append(self._export_use(
            definition,
            assignment,
            meta,
        ))

        self.reference_range_ids.extend(reference_range_ids)
        self._export_def_post_use(definition, meta, reference_range_ids)

    def _export_use(self, definition, assignment, meta):
        if definition.is_definition():
            range_id = meta.range_id
        else:
            range_id = self.emitter.emit_range(*make_ranges(definition))

        result_id = self.emitter.emit_definitionresult()
        hover_id = self.emitter.emit_hoverresult(wrap_contents(meta.contents))

        self.emitter.emit_next(range_id, meta.result_set_id)
        self.emitter.emit_textdocument_definition(meta.result_set_id, result_id)
        self.emitter.emit_item(result_id, [meta.range_id], self.document_id)
        self.emitter.emit_textdocument_hover(meta.result_set_id, hover_id)

        return range_id


class DefinitionMeta:
    def __init__(self, range_id, result_set_id, contents):
        self.range_id = range_id
        self.result_set_id = result_set_id
        self.contents = contents


def hash_source(source):
    return base64.b64encode(source.encode('utf-8')).decode()


def get_definitions(source, filename):
    return jedi.names(
        source,
        path=filename,
        all_scopes=True,
        references=True,
    )
