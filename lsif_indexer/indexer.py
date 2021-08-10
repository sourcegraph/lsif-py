"""Engine for indexing Python repos.

All the classes in this module that emit LSIF objects do so by yielding them,
so you can loop over one class's emit() generator and write each object to a
stream. Hopefully, keeping the writing out of all the classes makes this easier
to test.

One invariant to keep in mind is that LSIF expects ids to be monotonically
increasing, so as soon as you construct a model object, you should yield it
before doing anything else. Since this module uses dataclasses, keep in mind
that LSIF object members that are created at object construction time should be
yielded first before constructing any more (or at least, make sure they're
yielded in the right order).
"""

import base64
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from sys import stderr
from time import perf_counter
from typing import Iterable, Iterator, Optional

import click
import jedi
from jedi.api.classes import Name

from . import model

VERBOSITY = 0


@dataclass
class Timer:
    """Time a block of code.

    When the block ends, if verbosity is high enough, this prints a message and
    the time the block took.

    To change what the message is at the end, assign to self.description.
    """

    description: str
    verbosity: int
    begin: float = field(init=False)
    end: float = field(init=False)

    @property
    def elapsed_seconds(self) -> float:
        return self.end - self.begin

    def __enter__(self) -> "Timer":
        self.begin = perf_counter()
        return self

    def __exit__(self, *exc_info):
        self.end = perf_counter()
        if VERBOSITY >= self.verbosity:
            print(
                self.description,
                f"({self.elapsed_seconds:0.02f}s)",
                file=stderr,
            )


@dataclass
class Range:
    """A range is either a definition or a reference, for our purposes.

    This class handles translating between Jedi's understanding of a symbol
    location and LSIF's understanding (fencepost error on line number, and the
    fact that LSIF requires a begin and end position).

    Definition and Reference subclass this and know how to emit what they need,
    including the model.Range object in this superclass.
    """

    document_id: int
    name: Name
    range: model.Range = field(init=False)

    def __post_init__(self):
        self.range = model.Range(
            start=model.Position(line=self.line, character=self.lo),
            end=model.Position(line=self.line, character=self.hi),
        )

    @property
    def line(self) -> int:
        """The LSIF line number (0-indexed)."""
        return self.name.line - 1

    @property
    def lo(self) -> int:
        """The LSIF begin column (0-indexed, inclusive)."""
        return self.name.column

    @property
    def hi(self) -> int:
        """The LSIF end column (0-indexed, exclusive)."""
        return self.name.column + len(self.name.name)


@dataclass
class Definition(Range):
    """A location in a file that defines a symbol.

    This is a Range, it may have some references in its own file or in other
    files, and if it's an imported symbol, it may have a "next_definition",
    which is a Definition in another file that this Definition refers to.

    This class knows how to emit its own structure when it's defined, and how
    to emit all the reference edges to itself after we've indexed all files and
    know the total set of reference edges.
    """

    next_definition: Optional["Definition"]
    result_set: model.ResultSet = field(default_factory=model.ResultSet)
    references: dict[int, list[int]] = field(
        default_factory=lambda: defaultdict(list)
    )
    _ref_result_id: Optional[int] = field(default=None)

    @property
    def ref_result_id(self) -> int:
        if self._ref_result_id is None:
            raise RuntimeError(f"Expected ref_result_id for {self}")
        return self._ref_result_id

    def signatures(self) -> list[str]:
        """Get all possible signatures for this symbol as strings."""
        sigs = []
        for sig in self.name.get_signatures():
            try:
                sig_str = sig.to_string()
            except:  # noqa: E722
                # Some decorators confuse Jedi, ignore them
                continue
            else:
                sigs.append(sig_str)
        return sigs

    def docstring(self) -> str:
        """Get this symbol's docstring."""
        return self.name.docstring(raw=True, fast=False)

    def get_hover_result(self) -> Optional[model.HoverResult]:
        """Get this symbol's HoverResult.

        This is either one snippet per valid signature, or just the line of
        code that defines it if there aren't any signatures Jedi knows about,
        plus the docstring if it exists.
        """
        if signatures := self.signatures():
            hover_contents: list[model.HoverResultContent] = [
                model.Snippet(language="py", value=sig) for sig in signatures
            ]
        else:
            hover_contents = [
                model.Snippet(
                    language="py", value=self.name.get_line_code().strip()
                )
            ]
        if docstring := self.docstring():
            hover_contents.append(docstring)
        if hover_contents:
            return model.HoverResult(
                result=model.HoverResultContents(contents=hover_contents)
            )
        return None

    def emit(self) -> Iterable[model.LSIFEntry]:
        """Emit all the basic information about this Definition.

        This includes a ResultSet, the Range where this symbol is defined, and
        a DefinitionResult and ReferenceResult if this is the canonical
        location where it's defined, or a Next pointer to the real definition
        otherwise.
        """
        yield self.result_set
        yield self.range
        yield model.Next(out_v=self.range.id, in_v=self.result_set.id)

        if hover_result := self.get_hover_result():
            yield hover_result
            yield model.Hover(out_v=self.result_set.id, in_v=hover_result.id)

        if self.next_definition:
            yield model.Next(
                out_v=self.result_set.id,
                in_v=self.next_definition.result_set.id,
            )
        else:
            def_result = model.DefinitionResult()
            yield def_result
            yield model.Definition(
                out_v=self.result_set.id, in_v=def_result.id
            )
            yield model.Item(
                out_v=def_result.id,
                in_vs=[self.range.id],
                document=self.document_id,
                property="definitions",
            )

            ref_result = model.ReferenceResult()
            self._ref_result_id = ref_result.id
            yield ref_result
            yield model.Reference(out_v=self.result_set.id, in_v=ref_result.id)
        self.add_reference(self.document_id, self.range.id)

    def add_reference(self, document_id: int, range_id: int):
        """Record that a Reference edge should exist from this symbol.

        The arguments refer to the target of the edge. If this is not the
        canonical location of the Definition, we instead add the reference to
        the parent.

        These References will be output later, after processing all files, by
        emit_references.
        """
        if self.next_definition:
            self.next_definition.add_reference(document_id, range_id)
        else:
            self.references[document_id].append(range_id)

    def emit_references(self) -> Iterable[model.LSIFEntry]:
        """Write all the Item edges pointing to anything referencing this."""
        for doc_id, ref_ids in self.references.items():
            yield model.Item(
                out_v=self.ref_result_id,
                in_vs=ref_ids,
                document=doc_id,
                property="references",
            )


@dataclass
class Reference(Range):
    """A location in a file that refers to a symbol.

    This is a Range, and it knows where what it refers to was defined.
    """

    definition: Definition

    def emit(self) -> Iterable[model.LSIFEntry]:
        """Emit all the basic information about this Definition.

        If this Reference's target Definition is in the same file, we already
        have a valid ResultSet we can point to. If not, we need to create a
        ResultSet and make a Next edge that forwards from our ResultSet to the
        Definition's result set.
        """
        yield self.range
        if self.document_id == self.definition.document_id:
            result_set_id = self.definition.result_set.id
        else:
            result_set = model.ResultSet()
            yield result_set
            yield model.Next(
                out_v=result_set.id, in_v=self.definition.result_set.id
            )
            result_set_id = result_set.id
        yield model.Next(out_v=self.range.id, in_v=result_set_id)
        self.definition.add_reference(self.document_id, self.range.id)


DefinitionKey = tuple[int, int]


@dataclass
class DefinitionIndex:
    """Look up Definition objects by their Jedi location.

    This lets us take a jedi.Name that is a Reference, ask Jedi where it would
    go if we tried to jump to definition, then take the resulting location and
    look up the Definition object we've already got for that location.

    This lets us connect References to their corresponding Definitions, so we
    can emit the appropriate edges to connect them.
    """

    definitions: dict[DefinitionKey, Definition] = field(default_factory=dict)

    @staticmethod
    def name_key(name: Name) -> DefinitionKey:
        """Compute the index key for a jedi.Name."""
        return (name.line, name.column)

    def add(self, definition: Definition):
        """Add a Definition object to the index."""
        key = self.name_key(definition.name)
        if key in self.definitions:
            raise RuntimeError(f"{definition.name} at {key} already seen!")
        self.definitions[key] = definition

    def get(self, name: Name) -> Optional[Definition]:
        """Look up a Definition by a jedi.Name."""
        key = self.name_key(name)
        return self.definitions.get(key)

    def __iter__(self) -> Iterator[Definition]:
        """Iterate over all Definitions we know about."""
        return iter(self.definitions.values())


@dataclass(unsafe_hash=True)
class Document:
    """Everything we know about a file in a project.

    Knows how to index (emit LSIF objects) for everything in a file, and
    maintains an index of all symbols that file defines, so other files can
    look up those definitions.
    """

    script: jedi.Script = field(compare=False)
    filename: Path = field(init=False, compare=True)
    definitons: list[Name] = field(default_factory=list, compare=False)
    references: list[Name] = field(default_factory=list, compare=False)
    _id: Optional[int] = field(default=None, compare=False)
    definition_index: DefinitionIndex = field(
        default_factory=DefinitionIndex, compare=False
    )
    _dependencies: Optional[set["Document"]] = field(
        default=None, compare=False
    )

    def __post_init__(self):
        self.filename = self.script.path
        self.definitions = self.script.get_names(
            all_scopes=True, definitions=True, references=False
        )
        self.references = self.script.get_names(
            all_scopes=True, definitions=False, references=True
        )

    @property
    def id(self) -> int:
        if self._id is None:
            raise RuntimeError(f"Expected id for {self}")
        return self._id

    @property
    def indexed(self) -> bool:
        """We know a file has been indexed if it has an id set."""
        return self._id is not None

    def get_dependencies(self, project: "Project") -> set["Document"]:
        """Get the set of Documents this file has References to."""
        if self._dependencies is None:
            deps = set()
            for ref in self.references:
                for target in ref.goto():
                    def_filename = target.module_path
                    if dep := project.get_document(def_filename):
                        # If not, this isn't part of our project, it's maybe in
                        # a dependency library
                        if dep.filename != self.filename:
                            deps.add(dep)
            self._dependencies = deps
        return self._dependencies

    @property
    def base64_source(self) -> str:
        """Base64-encode the source content."""
        source = self.filename.read_bytes()
        return base64.b64encode(source).decode()

    def index(self, project: "Project") -> Iterable[model.LSIFEntry]:
        """Emits (yields) all the LSIF objects we need to for this file.

        Later, call emit_references() to emit Reference links from this file's
        symbols to its referrers.
        """
        with Timer(f"Indexing {self.filename}", 1) as timer:
            doc = model.Document(
                language_id="py",
                uri=f"file://{self.filename}",
                contents=self.base64_source,
            )
            yield doc
            self._id = doc.id
            yield model.Begin(scope="document", data=self.id)
            contains = []

            for definition in self.definitions:
                # Look up any definition this definition refers to (likely this
                # definition is importing a symbol from elsewhere). We just
                # want the first one, I think?
                next_definition = None
                for target in definition.goto():
                    filename = target.module_path
                    if filename == self.filename:
                        # Perhaps this should be an error? I don't think this
                        # can happen.
                        continue
                    if not (def_doc := project.get_document(filename)):
                        # Not a reference to other files in our repo.
                        continue
                    if other_definition := def_doc.get_definition(target):
                        # Got 'em.
                        next_definition = other_definition
                        break
                defn = Definition(
                    document_id=self.id,
                    name=definition,
                    next_definition=next_definition,
                )
                yield from defn.emit()
                self.definition_index.add(defn)
                contains.append(defn.range.id)

            for reference in self.references:
                # For every target Jedi might take us to, emit a Reference to
                # that location.
                for target in reference.goto():
                    filename = target.module_path
                    if not (def_doc := project.get_document(filename)):
                        # Not a reference to other files in our repo.
                        continue
                    if definition := def_doc.get_definition(target):
                        ref = Reference(
                            document_id=self.id,
                            name=reference,
                            definition=definition,
                        )
                        yield from ref.emit()
                        contains.append(ref.range.id)

            if contains:
                # The Go lsif-validate considers an empty inVs an error, so
                # don't emit a Contains edge unless we have some files.
                contains = list(sorted(set(contains)))
                yield model.Contains(out_v=self.id, in_vs=contains)
            yield model.End(scope="document", data=self.id)

            timer.description = f"Indexed {self.filename}"

    def emit_references(self) -> Iterable[model.LSIFEntry]:
        """Ask all definitions in this file to emit References.

        This shouldn't be called until we've indexed all files, so we know
        where all the References are.
        """
        with Timer(f"Cross-referencing {self.filename}", 1) as timer:
            for definition in self.definition_index:
                yield from definition.emit_references()
            timer.description = f"Cross-referenced {self.filename}"

    def get_definition(self, name: Name) -> Optional[Definition]:
        """Look for the definition of name in this file."""
        return self.definition_index.get(name)


class CircularDependencyError(Exception):
    """The project we're indexing has a circular import dependency."""

    def __init__(self, stack: list[Path], next: Path):
        self.stack = stack
        self.next = next
        self.message = "Circular dependency detected: " + " -> ".join(
            str(f) for f in self.stack + [self.next]
        )
        super().__init__(self.message)


@dataclass
class Project:
    """Everything we know about a repo, namely, files in it.

    This also has a jedi.Project that might know something interesting about
    how to construct a Python environment for this project, if, say, it has a
    virtualenv in an obvious location (this helps Jedi complete references).
    """

    root: Path
    exclude_dir: list[Path]
    project: jedi.Project = field(init=False)
    documents: dict[Path, Document] = field(default_factory=dict)
    project_id: int = field(init=False)

    def __post_init__(self):
        self.project = jedi.get_default_project(path=self.root)

    def emit_header(self) -> Iterable[model.LSIFEntry]:
        metadata = model.MetaData(
            project_root=f"file://{self.root}",
            tool_info=model.MetaData.ToolInfo(name="lsif-py"),
        )
        yield metadata
        project = model.Project()
        yield project
        self.project_id = project.id

    def index(self) -> Iterable[model.LSIFEntry]:
        """Load files and emit LSIF data for all the files in this Project.

        This includes indexing all documents in topological order (by import
        dependency), then emitting references for everything, together with the
        LSIF front- and back-matter.
        """
        with Timer("Loading files", 0) as timer:
            self.load_files()
            timer.description = f"Loaded {len(self.documents)} files"

        if VERBOSITY >= 1:
            print("Dependency graph:", file=stderr)
            for document in self.documents.values():
                print(
                    document.filename,
                    "->",
                    [dep.filename for dep in document.get_dependencies(self)],
                    file=stderr,
                )

        yield from self.emit_header()
        yield model.Begin(scope="project", data=self.project_id)
        to_index = set(self.documents.values())
        with Timer("Indexing", 0) as timer:
            yield from self.toposort_index(to_index)
            for document in self.documents.values():
                yield from document.emit_references()
            timer.description = f"Indexed {len(self.documents)} files"
        document_ids = list(
            sorted({document.id for document in self.documents.values()})
        )
        yield model.Contains(out_v=self.project_id, in_vs=document_ids)
        yield model.End(scope="project", data=self.project_id)

    def toposort_index(
        self, to_index: set[Document]
    ) -> Iterable[model.LSIFEntry]:
        """Call Document.index for each Document in topological order."""
        stack: list[Path] = []

        def try_to_index(document: Document):
            stack.append(document.filename)
            for dep in document.get_dependencies(self):
                if not dep.indexed:
                    if dep.filename in stack:
                        if (
                            dep.filename.name == "__init__.py"
                            and dep.filename.parent
                            in document.filename.parents
                        ):
                            # Always let a parent or sibling __init__.py
                            # go last, people often have circular
                            # dependencies in packages and their
                            # modules, we should ignore that and just
                            # index what we can.
                            continue
                        raise CircularDependencyError(stack, dep.filename)
                    to_index.discard(dep)
                    yield from try_to_index(dep)
                assert dep.indexed
            yield from document.index(self)
            stack.pop()

        while to_index:
            document = to_index.pop()
            yield from try_to_index(document)

    def load_files(self):
        """Load all files in the Project into Document objects."""
        filenames = self.root.glob("**/*.py")
        filenames = (
            filename
            for filename in filenames
            if not any(d in filename.parents for d in self.exclude_dir)
        )
        # I'm not sure, but I think Jedi works better if you make it load all
        # the files as Scripts first, then ask it questions, so we materialize
        # this list before asking any Document to index itself.
        scripts = [
            jedi.Script(path=filename, project=self.project)
            for filename in filenames
        ]
        for script in scripts:
            document = Document(script=script)
            self.documents[document.filename] = document

    def get_document(self, filename: Path) -> Optional[Document]:
        """Look up a Document in this Project by path."""
        return self.documents.get(filename)


@click.command()
@click.argument(
    "root",
    type=click.Path(
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        resolve_path=True,
        allow_dash=False,
    ),
)
@click.option("--file", type=click.File(mode="w"), default="data.lsif")
@click.option("--verbose/--quiet")
@click.option(
    "--exclude-dir", type=click.Path(resolve_path=True), multiple=True
)
def lsif_py(root: str, file, verbose: bool, exclude_dir: list[str]) -> None:
    global VERBOSITY
    if verbose:
        VERBOSITY += 1
    with Timer("Generating LSIF data", 0) as timer:
        project = Project(Path(root), [Path(s) for s in exclude_dir])
        for element in project.index():
            file.write(element.json())
            file.write("\n")
        timer.description = "Generated LSIF data"
