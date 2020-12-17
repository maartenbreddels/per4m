import argparse
import contextlib
import os
import runpy
import shlex
import subprocess
import signal
import sys
import time

import viztracer
import numpy


RETRIES = 10


usage = """

Run VizTracer and perf simultaneously. See also man perf record.

Usage:

$ perf-pyrecord -e cycles -m per4m.example2
"""

class PerfRecord:
    def __init__(self, output='perf.data', args=[], verbose=1, stacktrace=True, buffer_size="128M"):
        self.output = output
        self.buffer_size = buffer_size
        self.args = args
        self.stacktrace = stacktrace
        self.verbose = verbose

    def __enter__(self):
        self.start()
        return self

    def start(self):
        pid = os.getpid()
        # cmd = f"perf record -e 'sched:*' --call-graph dwarf -k CLOCK_MONOTONIC --pid {pid} -o {self.output}"
        perf_args = ' '.join(self.args)
        if self.stacktrace:
            perf_args += " --call-graph dwarf"
        cmd = f"perf record  {perf_args} -k CLOCK_MONOTONIC --pid {pid} -o {self.output}"
        if self.verbose >= 2:
            print(f"Running: {cmd}")
        args = shlex.split(cmd)
        self.perf = subprocess.Popen(args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        start_time = time.time()
        for _ in range(RETRIES):
            if os.path.exists(self.output):
                mtime = os.path.getmtime(self.output)
                if mtime > start_time:
                    break
            # we need to wait till perf creates the file
            time.sleep(0.1)
        else:
            self._finish()
            raise OSError(f'perf did not create {self.output}')
        start_size = os.path.getsize(self.output)
        for _ in range(RETRIES):
            size = os.path.getsize(self.output)
            if size > start_size:
                break
            # we need to wait till perf writes
            time.sleep(0.1)
        else:
            self._finish()
            raise OSError(f'perf did not write to {self.output}')
        # and give perf a bit more time
        time.sleep(0.05)
        return self

    def _finish(self):
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
        self.stop()

    def stop(self):
        self._finish()
        if self.verbose >= 1:
            print('Wait for perf to finish...')
        self.perf.wait()


@contextlib.contextmanager
def empty_context():
    yield


def main(argv=sys.argv):
    parser = argparse.ArgumentParser(argv[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=usage)
    parser.add_argument('--module', '-m')
    parser.add_argument('--import', dest="import_", help="Comma seperated list of modules to import before tracing (cleans up tracing output)")
    parser.add_argument('--verbose', '-v', action='count', default=1)
    parser.add_argument('--quiet', '-q', action='count', default=0)
    parser.add_argument('--output', '-o', dest="output", help="Output filename (default %(default)s)", default='perf.data')
    parser.add_argument('--output-viztracer', help="Output filename for viztracer (default %(default)s)", default='viztracer.json')

    parser.add_argument('--freq', '-F', help="Profile frequency, passed down to perf record (see man perf record)")
    parser.add_argument('--event', '-e', dest='events', help="Select PMU event, passed down to perf record (see man perf record)", action='append', default=[])

    parser.add_argument('--tracer_entries', type=int, default=1000000, help="See viztracer --help")

    # # these gets passed to stacktraceinject
    # parser.add_argument('--keep-cpython-evals', help="keep CPython evaluation stacktraces (instead of replacing) (default: %(default)s)", default=True, action='store_true')
    # parser.add_argument('--no-keep-cpython-evals', dest="keep_cpython_evals", action='store_false')
    # parser.add_argument('--allow-mismatch', help="Keep going even when we cannot match the C and Python stacktrace (default: %(default)s)", default=False, action='store_true')
    # parser.add_argument('--no-allow-mismatch', dest="allow_mismatch", action='store_false')
    # parser.add_argument('--pedantic', help="If false, accept known stack mismatch issues (default: %(default)s)", default=False, action='store_true')
    # parser.add_argument('--no-pedantic', dest="pedantic", action='store_false')

    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv[1:])
    verbose = args.verbose - args.quiet

    if args.import_:
        for module in args.import_.split(','):
            if verbose >= 2:
                print(f'importing {module}')
            __import__(module)

    viztracer_path = args.output_viztracer
    ctx = contextlib.redirect_stdout(None) if verbose == 0 else empty_context()
    perf_args = []
    if args.freq:
        perf_args.append(f' --freq={args.freq}')
    for event in args.events:
        perf_args.append(f' -e {event}')
    with ctx:
        with PerfRecord(verbose=verbose, args=perf_args) as perf:
            with viztracer.VizTracer(output_file=viztracer_path, verbose=verbose, tracer_entries=args.tracer_entries):
                if args.module:
                    runpy.run_module(args.module)
                else:
                    sys.argv = args.args
                    runpy.run_path(sys.argv[0])
    # forward = ""
    # if args.keep_cpython_evals:
    #     forward += ' --keep-cpython-evals'
    # else:
    #     forward += ' --no-keep-cpython-evals'
    # if args.allow_mismatch:
    #     forward += ' --allow-mismatch'
    # else:
    #     forward += ' --no-allow-mismatch'
    # if args.pedantic:
    #     forward += ' --pedantic'
    # else:
    #     forward += ' --no-pedantic'
    # if args.output:
    #     forward += ' --output=args.output'

    # cmd = f"perf script -i {perf.perf_output} --no-inline | per4m stacktraceinject {forward} --input {viztracer_path}"
    # if os.system(cmd) != 0:
    #     raise OSError(f'Failed to run perf or per4m perf2trace, command:\n$ {cmd}')


if __name__ == '__main__':
    main()
