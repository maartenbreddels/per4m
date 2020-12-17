import os
import tempfile
import viztracer
from viztracer.report_builder import ReportBuilder
from IPython.display import HTML, display

from IPython.core.magic import (cell_magic,
                                magics_class,
                                Magics,
                                needs_local_scope,
                                )


from .giltracer import PerfRecordGIL

@magics_class
class GilTraceMagic(Magics):
    @needs_local_scope
    @cell_magic
    def giltracer(self, line, cell, local_ns):
        temp_dir = tempfile.mkdtemp()
        perf_path = os.path.join(temp_dir, 'perf.data')
        viz_path = os.path.join(temp_dir, 'viztracer.json')
        gil_path = os.path.join(temp_dir, 'giltracer.json')
        out_path = 'giltracer.html'
        code = self.shell.transform_cell(cell)
        with PerfRecordGIL(perf_path, gil_path) as gt:
            with viztracer.VizTracer(output_file=viz_path):
                exec(code, local_ns, local_ns)
        gt.post_process()
        builder = ReportBuilder([viz_path, gil_path])
        builder.save(output_file=out_path)
        
        download = HTML(f'''<a href="{out_path}" download>Download {out_path}</a>''')
        view = HTML(f'''<a href="{out_path}" target="_blank" rel=”noopener noreferrer”>Open {out_path} in new tab</a> (might not work due to security issue)''')
        display(download, view)

def load_ipython_extension(ipython):
    """
    Use `%load_ext per4m.cellmagic`
    """
    ipython.register_magics(GilTraceMagic)