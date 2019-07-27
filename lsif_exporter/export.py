import os

from .consts import POSITION_ENCODING, PROTOCOL_VERSION
from .emitter import Emitter
from .file_export import FileExporter



def export(workspace, writer, verbose):
    """
    Read each python file (recursively) in the given path and
    write the analysis of each source file as an LSIF-dump to
    the given file writer.
    """
    uri = 'file://{}'.format(os.path.abspath(workspace))

    emitter = Emitter(writer)
    emitter.emit_metadata(PROTOCOL_VERSION, POSITION_ENCODING, uri)
    project_id = emitter.emit_project('py')

    file_count = 0
    for root, dirs, files in os.walk(workspace):
        for file in files:
            _, ext = os.path.splitext(file)
            if ext != '.py':
                continue

            file_count += 1
            path = os.path.join(root, file)
            FileExporter(path, emitter, project_id, verbose).export()

    if file_count == 0:
        print('No files found for export')
