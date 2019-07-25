from .emitter import Emitter
from .file_export import FileExporter


class Exporter:
    def __init__(self):
        self.emitter = Emitter()

    def export(self, filename):
        uri = 'TODO'  # TODO(efritz) - construct real uri
        self.emitter.emit_metadata('0.1.0', uri, 'utf-16')
        project_id = self.emitter.emit_project('py')
        self._export_file(filename, project_id)  # TODO(efritz) - support packages

    def _export_file(self, filename, project_id):
        FileExporter(self.emitter, project_id).export(filename)

    def print(self):
        self.emitter.print()


def export(filename):
    exporter = Exporter()
    exporter.export(filename)
    exporter.print()
