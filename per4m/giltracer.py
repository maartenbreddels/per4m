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

class GilTracer(PerfRecord):
    def __init__(self, output='perf.data', trace_output='giltracer.json', verbose=1):
        super().__init__(output=output, verbose=verbose, args=["-e 'sched:*'"])
        self.trace_output = trace_output
        self.verbose = verbose

    def __exit__(self, *args):
        super().__exit__(self, *args)
        verbose = '-q ' + '-v ' * self.verbose
        cmd = f"perf script -i {self.output} --no-inline | per4m perf2trace -o {self.trace_output} {verbose}"
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
    parser.add_argument('--output', '-o', dest="output", default='result.html', help="Output filename (default %(default)s)")
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv[1:])
    verbose = args.verbose - args.quiet

    if args.import_:
        for module in args.import_.split(','):
            if verbose >= 2:
                print(f'importing {module}')
            __import__(module)

    with GilTracer(verbose=verbose) as gt:
        with viztracer.VizTracer(output_file="viztracer.json", verbose=verbose):
            if args.module:
                runpy.run_module(args.module)
            else:
                sys.argv = args.args
                runpy.run_path(sys.argv[0])
    builder = ReportBuilder(['./viztracer.json', './giltracer.json'], verbose=verbose)
    builder.save(output_file=args.output)


if __name__ == '__main__':
    main()
