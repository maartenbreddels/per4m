import argparse
import os
import sys

import viztracer
from viztracer.report_builder import ReportBuilder

import runpy
from .record import PerfRecord


usage = """

Run VizTracer and perf simultaneously, then inject the GIL information in the viztracer output
Usage:

$ giltracer -m per4m.example1
"""

class PerfRecordSched(PerfRecord):
    def __init__(self, output='perf-sched.data', trace_output='schedtracer.json', verbose=1):
        super().__init__(output=output, verbose=verbose, args=["-e 'sched:*'"])
        self.trace_output = trace_output
        self.verbose = verbose

    def post_process(self, *args):
        verbose = '-q ' + '-v ' * self.verbose
        cmd = f"perf script -i {self.output} --no-inline | per4m perf2trace sched -o {self.trace_output} {verbose}"
        if self.verbose >= 1:
            print(cmd)
        if os.system(cmd) != 0:
            raise OSError(f'Failed to run perf or per4m perf2trace, command:\n$ {cmd}')


class PerfRecordGIL(PerfRecord):
    def __init__(self, output='perf-gil.data', trace_output='giltracer.json', viztracer_input="viztracer.json", verbose=1):
        # TODO: check output of perf probe --list="python:*gil*"  to see if probes are set
        super().__init__(output=output, verbose=verbose, args=["-e 'python:*gil*'"], stacktrace=False)
        # this is used to filter the giltracer data
        self.viztracer_input = viztracer_input
        self.trace_output = trace_output
        self.verbose = verbose

    def post_process(self, *args):
        verbose = '-q ' + '-v ' * self.verbose
        # -i {self.viztracer_input}   # we don't use this ftm
        cmd = f"perf script -i {self.output} --no-inline --ns | per4m perf2trace gil -o {self.trace_output} {verbose}"
        if self.verbose >= 1:
            print(cmd)
        if os.system(cmd) != 0:
            raise OSError(f'Failed to run perf or per4m perf2trace, command:\n$ {cmd}')

def main(argv=sys.argv):
    parser = argparse.ArgumentParser(argv[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=usage)
    parser.add_argument('--module', '-m')
    parser.add_argument('--import', dest="import_", help="Comma seperated list of modules to import before tracing (cleans up tracing output)")
    parser.add_argument('--verbose', '-v', action='count', default=1)
    parser.add_argument('--quiet', '-q', action='count', default=0)
    parser.add_argument('--output', '-o', dest="output", default='giltracer.html', help="Output filename (default %(default)s)")
    parser.add_argument('--state-detect', help="Use perf sched events to detect if a process is sleeping due to the GIL (default: %(default)s)", default=False, action='store_true')
    parser.add_argument('--no-state-detect', dest="state_detect", action='store_false')
    parser.add_argument('--gil-detect', help="Use uprobes to detect who has the GIL (read README.md) (default: %(default)s)", default=True, action='store_true')
    parser.add_argument('--no-gil-detect', dest="gil_detect", action='store_false')

    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv[1:])
    verbose = args.verbose - args.quiet

    if args.import_:
        for module in args.import_.split(','):
            if verbose >= 2:
                print(f'importing {module}')
            __import__(module)

    perf1 = PerfRecordSched(verbose=verbose) if args.state_detect else None
    perf2 = PerfRecordGIL(verbose=verbose) if args.gil_detect else None
    vt = viztracer.VizTracer(output_file="viztracer.json", verbose=verbose)

    # pass on the rest of the arguments
    sys.argv = args.args
    if args.module:
        module = runpy.run_module(args.module)
    else:
        module = runpy.run_path(sys.argv[0])

    if perf1:
        perf1.start()
    if perf2:
        perf2.start()

    try:
        vt.start()
        module['main'](args.args)
    finally:
        vt.stop()
        if perf1:
            perf1.stop()
        if perf2:
            perf2.stop()
        vt.save('viztracer.json')
        if perf1:
            perf1.post_process()
        if perf2:
            perf2.post_process()

    files = ['viztracer.json']
    if perf1:
        files.append('schedtracer.json')
    if perf2:
        files.append('giltracer.json')
    builder = ReportBuilder(files, verbose=verbose)
    builder.save(output_file=args.output)


if __name__ == '__main__':
    main()
