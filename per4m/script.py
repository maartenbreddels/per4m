import argparse
import json
import shlex
import subprocess
import sys

from viztracer.prog_snapshot import ProgSnapshot


from .perfutils import read_events, parse_header

usage = """

Take stacktraces from VizTracer, and inject them in perf script output

Usage:

$ perf-pyscript | per4m stacktraceinject --input viztracer.json
"""

def print_stderr(*args):
    print(*args, file=sys.stderr)

def stacktrace_inject(stacktrace, snapshot, pid, time, keep_cpython_evals=False, perror=print_stderr, allow_mismatch=False, pedantic=False):
    # we'll do in place modification
    stacktrace = stacktrace.copy()
    # First, we build op parts of the callstack from VizTracers
    # We can go into and out of Python/C several times
    pystacktraces = [[]]
    pystacktrace_part = pystacktraces[-1]

    snapshot.goto_tid(pid)
    snapshot.goto_timestamp(time)
    bottom_frame = frame = snapshot.curr_frame
    was_in_python = frame.node.is_python
    while frame:
        node = frame.node
        # output should become sth like: ffffffff9700008c entry_SYSCALL_64_after_hwframe+0x44 ([kernel.kallsyms])
        filename = node.filename
        if filename is None:
            location = ''
        else:
            if 'frozen' in filename:
                filename = '<frozen>'
            location = f"::{filename}:{node.lineno}"
        funcname = node.funcname or node.fullname
        if node.is_python:
            type = 'py'
        else:
            type = 'cext'
        # lineno = f':{node.lineno}' if node.lineno is not None else ''
        if node.is_python:
            if not was_in_python:
                # this is a jump back to into c, which we allow
                # pystacktraces.append([])
                # pystacktrace_part = pystacktraces[-1]
                pass
        else:
            if was_in_python:
                # this is a jump into Python
                pystacktraces.append([])
                pystacktrace_part = pystacktraces[-1]
        pystacktrace_part.append(f'000000000000000000000000 {type}::{funcname}{location} ([{filename}])')
        was_in_python = node.is_python
        frame = frame.parent
    
    # Next, we find where in the perf output, we were in the Python evaluate loop (multiple places possible)
    # A list of (index_min, index_max) where the Python stacktraces should be injected/replaced
    pyslices = []

    index_min = None
    index_max = None
    is_py = [False] * len(stacktrace)
    # The C Part of Python callstack should begin with a function with this name in it
    begin_functions = ['PyEval_Eval']
    # and all function call after that may be one that contains these names
    continue_functions = ['PyEval_Eval', 'PyFunction_FastCall', 'function_code_fastcall', 'method_call', 'call_function', 'PyCFunction_FastCall', 'PyObject_FastCall']
    # we could make the code simpler by flipping the stacktrace, so the bottom of the stack starts at index 0
    # (instead of reversed)
    for i, call in enumerate(stacktrace[::-1]):
        i = len(stacktrace) - i - 1
        # Or we found the beginning, or a continuation of the evaluation loop
        if (index_max is None and any(sig in call for sig in begin_functions)) or\
            (index_max is not None and any(sig in call for sig in continue_functions)):
            if index_max is None:
                index_max = i
            index_min = i
        else:
            if index_max is not None:
                pyslices.append((index_min, index_max))
                is_py[index_min:index_max] = [True] * (index_max - index_min)
                index_min = index_max = None
    if index_max is not None:
        pyslices.append((index_min, index_max))
    
    # Lets give some nice output in case it does not match up
    if len(pystacktraces) != len(pyslices):
        if not pedantic:
            # for these we know that we often get a mismatch, and they seem reasonable to ignore
            known_failures = ['pythread_wrapper', 'switch_fpu_return', 'do_fork', 'ret_from_fork', 'start_thread']
            for known_failure in known_failures:
                if any(known_failure in call for call in stacktrace) and not any('_Py' in call for call in stacktrace):
                    perror(f'Seen {known_failure} in stacktrace during, silently ignoring the stack mismatch, use --no-pedantic to not ignore this')
                    return stacktrace
        perror(f"OOOOPS, could not match stacktraces at time {time} for pid {pid}!")
        perror("Where VizTracer thinks we are:")
        perror(bottom_frame.node.fullname)
        try:
            bottom_frame.show(perror)
        except:
            perror('Oops, viztracer fails showing')
        # snap.where()
        perror("Callstack slices where we think we should inject the Python callstack:")
        for pyslice in pyslices:
            perror(pyslice)
        perror("Callstack from perf, where * indicates where we think the Python eval loop is:")
        for i, call in enumerate(stacktrace):
            perror(i, '*' if is_py[i] else ' ', call)
        
        perror("Python call stacks, as found from VizTracer:")
        for pystacktraces_part in pystacktraces:
            perror('-----')
            for i, call in enumerate(pystacktraces_part):
                perror(call)
        perror('-----')
        if not allow_mismatch:
            raise ValueError('Stack traces from VizTracer and perf could not be matched, run with --allow-mismatch and inspect output carefully')
    else:
        for pyslice, pystacktraces_part in zip(pyslices, reversed(pystacktraces)):
            index_min, index_max = pyslice
            if keep_cpython_evals:
                for i in range(index_min, index_max+1):
                    ptr, call = stacktrace[i].split(' ', 1)
                    stacktrace[i] = f'{ptr} cpyeval::{call}'
            else:
                # mark for delection, to avoid indices getting messed up
                stacktrace[index_min:index_max+1] = [None] * (index_max - index_min + 1)
            for pystack in reversed(pystacktraces_part):
                stacktrace.insert(index_min, pystack)
        stacktrace = [k for k in stacktrace if k is not None]
    return stacktrace


def main(argv=sys.argv):
    parser = argparse.ArgumentParser(argv[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=usage)
    parser.add_argument('--verbose', '-v', action='count', default=0)  # by default quiet, since we write to stdout
    parser.add_argument('--quiet', '-q', action='count', default=0)
    parser.add_argument('--keep-cpython-evals', help="keep CPython evaluation stacktraces (instead of replacing) (default: %(default)s)", default=False, action='store_true')
    parser.add_argument('--no-keep-cpython-evals', dest="keep_cpython_evals", action='store_false')
    parser.add_argument('--allow-mismatch', help="Keep going even when we cannot match the C and Python stacktrace (default: %(default)s)", default=False, action='store_true')
    parser.add_argument('--no-allow-mismatch', dest="allow_mismatch", action='store_false')
    parser.add_argument('--pedantic', help="If false, accept known stack mismatch issues (default: %(default)s)", default=False, action='store_true')
    parser.add_argument('--no-pedantic', dest="pedantic", action='store_false')
    parser.add_argument('--input', '-i', help="VizTracer input (default %(default)s)", default="viztracer.json")
    parser.add_argument('--output', '-o', dest="output", default=None, help="Output filename (default %(default)s)")
    

    args = parser.parse_args(argv[1:])
    verbose = args.verbose - args.quiet

    perf_script_args = ['--no-inline']
    perf_script_args = ' '.join(perf_script_args)
    cmd = f"perf script {perf_script_args}"
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
    with open(args.input, "r") as f:
        json_data = f.read()
    snap = ProgSnapshot(json_data)
    # find all pids (or tids)
    pids = list(snap.func_trees)
    for pid in pids.copy():
        pids.extend(list(snap.func_trees[pid]))
    t0 = min(event['ts'] for event in json.loads(json_data)['traceEvents'])
    
    for header, stacktrace in read_events(perf.stdout):
        print(header, file=output)
        values, _, _ = parse_header(header)
        time = values['time'] - t0
        triggerpid = values['triggerpid']
        if triggerpid in pids:
            try:
                stacktrace = stacktrace_inject(stacktrace, snap, triggerpid, time, keep_cpython_evals=args.keep_cpython_evals, allow_mismatch=args.allow_mismatch, pedantic=args.pedantic)
                for call in stacktrace:
                    print(call, file=output)
            except:
                print(f"Error for event: {header}")
                raise
        print(file=output)

