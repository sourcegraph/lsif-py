import base64
import contextlib
import os

from .analysis import get_names
from .emitter import Emitter, FileWriter
from .consts import (
    INDENT, MAX_HIGHLIGHT_RANGE,
    POSITION_ENCODING, PROTOCOL_VERSION,
)


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
        self.definition_result_id = 0


class FileIndexer:
    """
    Analysis the definitions and uses in the given file and
    add an LSIF document to the emitter. As analysis is done
    on a per-file basis, this class holds the majority of the
    indexer logic.
    """
    def __init__(self, filename, emitter, project_id, verbose, exclude_content):
        self.filename = filename
        self.emitter = emitter
        self.project_id = project_id
        self.verbose = verbose
        self.exclude_content = exclude_content
        self.definition_metas = {}

    def index(self):
        print('Indexing file {}'.format(self.filename))

        with open(self.filename) as f:
            source = f.read()
        self.source_lines = source.split('\n')

        document_args = [
            'py',
            'file://{}'.format(os.path.abspath(self.filename)),
        ]

        if not self.exclude_content:
            encoded = base64.b64encode(source.encode('utf-8')).decode()
            document_args.append(encoded)

        self.document_id = self.emitter.emit_document(*document_args)

        with scope_events(self.emitter, 'document', self.document_id):
            self._index(source)

    def _index(self, source):
        # Do an initial analysis to get a list of names from
        # the source file. Some additional analysis may be
        # done lazily in later steps when needed.

        self.names = get_names(source, self.filename)

        if self.verbose:
            print('{}Searching for defs'.format(INDENT))

        # First emit everything for names defined in this
        # file. This needs to be done first as edges need
        # to be emitted only after both of their adjacent
        # vertices (i.e. defs must be emitted before uses).

        for name in self.names:
            if name.is_definition():
                self._export_definition(name)

        if self.verbose:
            print('{}Searching for uses'.format(INDENT))

        # Next, we can emit uses. Some of these names may
        # reference a definition from another file or a
        # builtin. The procedure below must account for
        # these cases.

        for name in self.names:
            self._export_uses(name)

        # Next, do any additional linking that we need to
        # do now that both definition and their uses are
        # emitted. Mainly, this populates hover tooltips
        # for uses.

        for definition, meta in self.definition_metas.items():
            self._link_uses(definition, meta)

        # Finally, link uses to their containing document
        self._emit_contains()

    def _export_definition(self, name):
        """
        Emit vertices and edges related directly to the definition of
        or assignment to a variable. Create a definition meta object
        with the generated LSIF identifiers and make it queryable by
        the same definition object.
        """
        contents = [{
            'language': 'py',
            'value': extract_text(self.source_lines, name),
        }]

        docstring = name.docstring
        if docstring:
            contents.append(docstring)

        # Emit hover tooltip and link it to a result set so that we can
        # re-use the same node for hover tooltips on usages.
        hover_id = self.emitter.emit_hoverresult({'contents': contents})
        result_set_id = self.emitter.emit_resultset()
        self.emitter.emit_textdocument_hover(result_set_id, hover_id)

        # Link result set to range
        range_id = self.emitter.emit_range(*make_ranges(name))
        self.emitter.emit_next(range_id, result_set_id)

        # Stash the identifiers generated above so we can use then
        # when exporting related uses.
        self.definition_metas[name] = DefinitionMeta(
            range_id,
            result_set_id,
            contents,
        )

        # Print progress
        self._debug_def(name)

    def _export_uses(self, name):
        """
        Emit vertices and edges related to any use of a definition.
        The definition must have already been exported by the above
        procedure.
        """
        try:
            definitions = name.definitions()
        except Exception as ex:
            raise
            print('Failed to retrieve definitions: {}'.format(str(ex)))
            return

        for definition in definitions:
            self._export_use(name, definition)

    def _export_use(self, name, definition):
        """
        Emit vertices and edges directly related to a single use of
        a definition.
        """
        meta = self.definition_metas.get(definition)
        if not meta:
            return

        # Print progress
        self._debug_use(name, definition)

        if name.is_definition():
            # The use and the definition are the same. It is against
            # spec to have overlapping or duplicate ranges in a single
            # document, so we re-use the one that we had generated
            # previously.
            range_id = meta.range_id
        else:
            # This must be a unique name, generate a new range vertex
            range_id = self.emitter.emit_range(*make_ranges(name))

        # Link use range to definition resultset
        self.emitter.emit_next(range_id, meta.result_set_id)

        if not meta.definition_result_id:
            result_id = self.emitter.emit_definitionresult()
            self.emitter.emit_textdocument_definition(meta.result_set_id, result_id)
            meta.definition_result_id = result_id

        self.emitter.emit_item(meta.definition_result_id, [meta.range_id], self.document_id)

        # Bookkeep this reference for the link procedure below
        meta.reference_range_ids.add(range_id)

    def _link_uses(self, name, meta):
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

    def _debug_def(self, name):
        if not self.verbose:
            return

        print('{}Def #{}, line {}: {}'.format(
            INDENT * 2,
            self.definition_metas.get(name).range_id,
            name.line + 1,
            highlight_range(self.source_lines, name).strip()),
        )

    def _debug_use(self, name, definition):
        if not self.verbose or name == definition:
            return

        print('{}Use of #{}, line {}: {}'.format(
            INDENT * 2,
            self.definition_metas.get(definition).range_id,
            name.line + 1,
            highlight_range(self.source_lines, name),
        ))


def index(workspace, writer, verbose, exclude_content):
    """
    Read each python file (recursively) in the given path and
    write the analysis of each source file as an LSIF-dump to
    the given file writer.
    """
    uri = 'file://{}'.format(os.path.abspath(workspace))

    emitter = Emitter(FileWriter(writer))
    emitter.emit_metadata(PROTOCOL_VERSION, POSITION_ENCODING, uri)
    project_id = emitter.emit_project('py')

    with scope_events(emitter, 'project', project_id):
        file_count = 0
        for root, dirs, files in os.walk(workspace):
            for file in files:
                _, ext = os.path.splitext(file)
                if ext != '.py':
                    continue

                file_count += 1
                path = os.path.join(root, file)

                FileIndexer(
                    path,
                    emitter,
                    project_id,
                    verbose,
                    exclude_content,
                ).index()

    if file_count == 0:
        print('No files found to index')


@contextlib.contextmanager
def scope_events(emitter, scope, id):
    emitter.emit_event('begin', scope, id)
    yield
    emitter.emit_event('end', scope, id)


def make_ranges(name):
    """
    Return a start and end range values for a range vertex.
    """
    return (
        {'line': name.line, 'character': name.lo},
        {'line': name.line, 'character': name.hi},
    )


def extract_text(source_lines, name):
    """
    Extract the text at the range described by the given name.
    """
    # TODO(efritz) - highlight span
    return source_lines[name.line].strip()


def highlight_range(source_lines, name):
    """
    Return the source line where the name occurs with the range
    described by the name highlighted with an ANSI code.
    """
    lo, hi = name.lo, name.hi
    trimmed_lo, trimmed_hi = False, False

    # Right-most whitespace is meaningless
    line = source_lines[name.line].rstrip()

    # Left-most whitespace is also meaningless, but we have
    # to be a bit more careful to maintain the correct range
    # of the highlighted region relative to the line.

    while line and line[0] in [' ', '\t']:
        line = line[1:]
        lo, hi = lo - 1, hi - 1

    # While we have more characters than we want AND the size
    # of the highlighted portion can be reduced to below this
    # size, try trimming single characters from the end of the
    # string and leave the highlighted portion somewhere in the
    # middle.

    while len(line) > MAX_HIGHLIGHT_RANGE and (hi - lo) < MAX_HIGHLIGHT_RANGE:
        trimmable_lo = lo > 0
        trimmable_hi = len(line) - hi - 1

        if trimmable_lo > 0 and trimmable_lo >= trimmable_hi:
            line = line[1:]
            lo, hi = lo - 1, hi - 1
            trimmed_lo = True

        if trimmable_hi > 0 and trimmable_hi >= trimmable_lo:
            line = line[:-1].rstrip()
            trimmed_hi = True

    return '{}{}\033[4;31m{}\033[0m{}{}'.format(
        '... ' if trimmed_lo else '',
        line[:lo].lstrip(),
        line[lo:hi],
        line[hi:].rstrip(),
        ' ...' if trimmed_hi else '',
    )
