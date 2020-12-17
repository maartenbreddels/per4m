import argparse
import json
import shlex
import subprocess
import sys

from viztracer.prog_snapshot import ProgSnapshot


from .perfutils import read_events, parse_header
from .script import stacktrace_inject, print_stderr
from .perf2trace import perf2trace


usage = """

Take stacktraces from VizTracer, and inject them in perf script output and print out stack traces with weights for stackcollapse.pl
(from https://github.com/brendangregg/FlameGraph )

Usage:

# for this we need the process states, and we can skip the GIL detection for performance
$ giltracer --no-gil-detect --state-detect -m per4m.example3

# offgil will use perf-sched.data
$ offgil | ~/github/FlameGraph/stackcollapse.pl | ~/github/FlameGraph/flamegraph.pl --countname=us --title="Off-GIL Time Flame Graph" --colors=python > offgil.svg
"""


def main(argv=sys.argv):
    parser = argparse.ArgumentParser(argv[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=usage)
    parser.add_argument('--verbose', '-v', action='count', default=0)  # by default quiet, since we write to stdout
    parser.add_argument('--quiet', '-q', action='count', default=0)
    parser.add_argument('--state', help='State to match (default: %(default)s)', default="S(GIL)")
    parser.add_argument('--strip-take-gil', dest="strip_take_gil", help="Remove everything from the stack above take_gil (default: %(default)s)", default=True, action='store_true')
    parser.add_argument('--no-strip-take-gil', dest="strip_take_gil", action='store_false')
    parser.add_argument('--keep-cpython-evals', help="keep CPython evaluation stacktraces (instead of replacing) (default: %(default)s)", default=False, action='store_true')
    parser.add_argument('--no-keep-cpython-evals', dest="keep_cpython_evals", action='store_false')
    parser.add_argument('--allow-mismatch', help="Keep going even when we cannot match the C and Python stacktrace (default: %(default)s)", default=False, action='store_true')
    parser.add_argument('--no-allow-mismatch', dest="allow_mismatch", action='store_false')
    parser.add_argument('--pedantic', help="If false, accept known stack mismatch issues (default: %(default)s)", default=False, action='store_true')
    parser.add_argument('--no-pedantic', dest="pedantic", action='store_false')
    parser.add_argument('--input-perf', help="Perf input (default %(default)s)", default="perf-sched.data")
    parser.add_argument('--input-viztracer', help="VizTracer input (default %(default)s)", default="viztracer.json")
    parser.add_argument('--output', '-o', dest="output", default=None, help="Output filename (default %(default)s)")
    

    args = parser.parse_args(argv[1:])
    verbose = args.verbose - args.quiet

    perf_script_args = ['--no-inline']
    perf_script_args = ' '.join(perf_script_args)
    cmd = f"perf script {perf_script_args} -i {args.input_perf}"
    if verbose >= 2:
        print(f"Running: {cmd}")
    perf_args = shlex.split(cmd)
    perf = subprocess.Popen(perf_args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) #, stdin=subprocess.PIPE)

    if args.output is None:
        output = sys.stdout
    else:
        output = open(args.output, "w")
    
    if verbose >= 1:
        print_stderr("Loading snapshot")
    with open(args.input_viztracer, "r") as f:
        json_data = f.read()
    snap = ProgSnapshot(json_data)
    # find all pids (or tids)
    pids = list(snap.func_trees)
    for pid in pids.copy():
        pids.extend(list(snap.func_trees[pid]))
    t0 = min(event['ts'] for event in json.loads(json_data)['traceEvents'] if 'ts' in event)
    
    for header, stacktrace, event in perf2trace(perf.stdout, verbose):
        if event['name'] == args.state:
            values, _, _ = parse_header(header)
            time = values['time'] - t0
            triggerpid = event['tid']
            if triggerpid in pids:
                try:
                    stacktrace = stacktrace_inject(stacktrace, snap, triggerpid, time, keep_cpython_evals=args.keep_cpython_evals, allow_mismatch=args.allow_mismatch, pedantic=args.pedantic)
                    if args.strip_take_gil:
                        take_gil_index = None
                        for i, call in enumerate(stacktrace):
                            if 'take_gil' in call:
                                take_gil_index = i
                        if take_gil_index is not None:  # shouldn't it be always there?
                            stacktrace = stacktrace[take_gil_index:]
                    for call in stacktrace:
                        ptr, signature = call.split(' ', 1)
                        print(signature, file=output)
                except:
                    print_stderr(f"Error for event: {header}")
                    raise
            print(int(event['dur']))
            print(file=output)

