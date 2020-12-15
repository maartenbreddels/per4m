import argparse
import os
import shlex
import subprocess
import sys
import time
import signal


import viztracer
from viztracer.report_builder import ReportBuilder

import runpy


RETRIES = 10


usage = """

Convert perf.data to Trace Event Format.

Usage:

$ per4m giltracer -m per4m.example1
"""

class GilTracer:
    def __init__(self, perf_output='perf.data', trace_output='giltracer.json', verbose=1):
        self.perf_output = perf_output
        self.trace_output = trace_output
        self.verbose = verbose

    def __enter__(self):
        pid = os.getpid()
        cmd = f"perf record -e 'sched:*' --call-graph dwarf -k CLOCK_MONOTONIC --pid {pid} -o {self.perf_output}"
        if self.verbose >= 2:
            print(f"Running: {cmd}")
        args = shlex.split(cmd)
        self.perf = subprocess.Popen(args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        start_time = time.time()
        for _ in range(RETRIES):
            if os.path.exists(self.perf_output):
                mtime = os.path.getmtime(self.perf_output)
                if mtime > start_time:
                    break
            # we need to wait till perf creates the file
            time.sleep(0.1)
        else:
            self.finish()
            raise OSError(f'perf did not create {self.perf_output}')
        start_size = os.path.getsize(self.perf_output)
        for _ in range(RETRIES):
            size = os.path.getsize(self.perf_output)
            if size > start_size:
                break
            # we need to wait till perf writes
            time.sleep(0.1)
        else:
            self.finish()
            raise OSError(f'perf did not write to {self.perf_output}')
        # and give perf a bit more time
        time.sleep(0.05)
        return self

    def finish(self):
        self.perf.terminate()
        outs, errs = self.perf.communicate(timeout=5)
        if self.verbose >= 1:
            print(outs.decode('utf8'))
        if errs:
            if self.verbose >= 1:
                print(errs.decode('utf8'))
        if self.perf.returncode not in [0, -signal.SIGTERM.value]:
            print(signal.SIGTERM)
            raise OSError(f'perf record fails, got exit code {self.perf.returncode}')

    def __exit__(self, *args):
        self.finish()
        if self.verbose >= 1:
            print('Wait for perf to finish...')
        self.perf.wait()

        pid = os.getpid()
        verbose = '-q ' + '-v ' * self.verbose
        cmd = f"perf script -i {self.perf_output} --no-inline | per4m perf2trace -o {self.trace_output} {verbose}"
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
