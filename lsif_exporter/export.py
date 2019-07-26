import os

from .consts import PROTOCOL_VERSION
from .emitter import Emitter
from .file_export import FileExporter


class Exporter:
    def __init__(self, workspace):
        self.workspace = workspace
        self.emitter = Emitter()

    def export(self, filename):
        uri = 'TODO'  # TODO(efritz) - construct real uri
        self.emitter.emit_metadata('0.1.0', uri, 'utf-16')
        project_id = self.emitter.emit_project('py')
        self._export_files_recursively(project_id)
        return self

    def _export_files_recursively(self, project_id):
        for root, dirs, files in os.walk(self.workspace):
            for file in files:
                _, ext = os.path.splitext(file)
                if ext != '.py':
                    continue

                self._export_file(os.path.join(root, file), project_id)

    def _export_file(self, filename, project_id):
        FileExporter(self.emitter, project_id).export(filename)

    def print(self):
        return self.emitter.print()


def export(workspace):
    return Exporter(workspace).export().print()
