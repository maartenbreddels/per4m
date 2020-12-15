import sys
import json
import argparse


def read_events(input):
    first_line = True
    stacktrace = []
    header = None
    for line in sys.stdin:
        line = line.strip()
        if first_line:
            header = line
            stacktrace = []
            first_line = False
        else:
            if not line:  # done
                yield header, stacktrace
                first_line = True
                continue
            stacktrace.append(line)


def parse_values(parts, **types):
    values = {}
    for part in parts:
        if "=" in part:
            key, value = part.split('=', 1)
            value = types.get(key, str)(value)
            values[key] = value
    for key in types:
        if key not in values:
            raise ValueError(f'Expected to find key {key} in {parts}')
    return values


def in_stacktrace(function_name, stacktrace):
    return any(function_name in call for call in stacktrace)


def takes_gil(stacktrace):
    return in_stacktrace('take_gil', stacktrace)


def drops_gil(stacktrace):
    return in_stacktrace('drop_gil', stacktrace)


usage = """

Convert perf.data to Trace Event Format.

Usage:

Always run perf with -e 'sched:*' --call-graph dwarf -k CLOCK_MONOTONIC, the rest of the events are extra
$ perf record -e 'sched:*' --call-graph dwarf -k CLOCK_MONOTONIC -e L1-dcache-load-misses -e instructions -e cycles -e page-faults -- python -m per4m.example1 
Run with --no-online, otherwise it may run slow
$ perf script --no-inline | per4m perf2trace --no-running -o example1perf.json
$ viztracer --combine example1.json example1perf.json -o example1.html
"""

def main(argv=sys.argv):
    parser = argparse.ArgumentParser(argv[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        usage=usage)
    parser.add_argument('--verbose', '-v', action='count', default=1)
    parser.add_argument('--quiet', '-q', action='count', default=0)
    parser.add_argument('--sleeping', help="store sleeping phase (default: %(default)s)", default=True, action='store_true')
    parser.add_argument('--no-sleeping', dest="sleeping", action='store_false')
    parser.add_argument('--running', help="show running phase (default: %(default)s)", default=False, action='store_true')
    parser.add_argument('--no-running', dest="running", action='store_false')
    parser.add_argument('--all-tracepoints', help="store all tracepoints phase (default: %(default)s)", default=False, action='store_true')

    parser.add_argument('--output', '-o', dest="output", default='perf.json', help="Output filename (default %(default)s)")


    args = parser.parse_args(argv[1:])

    trace_events = []

    # useful for debugging, to have the pids a name
    pid_names = {}
    # pid_names = {872068: "main", 872070: "t1", 872071: "t2"}
    # a bit pendantic to keep these separated
    last_run_time = {}
    last_sleep_time = {}
    last_sleep_stacktrace = {}
    verbose = args.verbose - args.quiet
    time_first = None
    store_runing = args.running
    store_sleeping = args.sleeping
    parent_pid = {}  # maps pid/tid to the parent
    count = None
    for header, stacktrace in read_events(sys.stdin):
        try:
            if args.verbose >= 3:
                print(header)
            pid = None
            parts = header.split()
            # python 302629 [011] 3485124.180312:       sched:sched_switch: prev_comm=python prev_pid=302629 prev_prio=120 prev_state=S ==> next_comm=swapper/11 next_pid=0 next_prio=120
            event = parts[4][:-1] # strip off ':'
            if ":" in event:  # tracepoint
                dso, triggerpid, cpu, time, _, *other = parts
                tracepoint = True
            else:  # counter etc
                dso, triggerpid, time, count, _, *other = parts
                tracepoint = False
            triggerpid = int(triggerpid)
            time = float(time[:-1]) * 1e6
            if time_first is None:
                time_first = time
            def log(*args, time=time/1e6):
                offset = time - time_first/1e6
                print(f"{time:13.6f}[+{offset:5.4f}]", *args)
            if args.all_tracepoints and tracepoint:
                trace_events.append({'name': event, 'pid': parent_pid.get(pid, pid), 'tid': triggerpid, 'ts': time, 'ph': 'i', 's': 'g'})
            first_line = False
            gil_event = None
            if event == "sched:sched_switch":
                # e.g. python 393320 [040] 3498299.441431:                sched:sched_switch: prev_comm=python prev_pid=393320 prev_prio=120 prev_state=S ==> next_comm=swapper/40 next_pid=0 next_prio=120
                try:
                    values = parse_values(parts, prev_pid=int)
                    pid = values['prev_pid']
                    prev_state = values['prev_state']
                except ValueError:
                    # perf 4
                    comm, pid = other[0].rsplit(':', 1)
                    pid = int(pid)
                    prev_state = other[2]
                # we are going to sleep?
                if prev_state == 'R':
                    # this happens when a process just started, so we just set the start time
                    last_sleep_time[pid] = time
                    continue
                # if values['prev_comm'] != "python":
                #     if verbose >= 2:
                #         log(f'Skipping switch from {values["prev_comm"]}')
                name = pid_names.get(pid, pid)
                if pid not in last_run_time:
                    # raise ValueError(f'pid {pid} not seen running before, only {last_run_time}')
                    continue
                dur = time  - last_run_time[pid]
                if verbose >= 2:
                    log(f'{name} will switch to state={prev_state}, ran for {dur}')
                if store_runing:
                    event = {"pid": parent_pid.get(pid, pid), "tid": pid, "ts": last_run_time[pid], "dur": dur, "name": 'R', "ph": "X", "cat": "process state"}
                    trace_events.append(event)

                last_sleep_time[pid] = time
                last_sleep_stacktrace[pid] = stacktrace
                del last_run_time[pid]
            elif event == "sched:sched_wakeup":
                # e.g: swapper     0 [040] 3498299.642199:                sched:sched_waking: comm=python pid=393320 prio=120 target_cpu=040
                prev_state = None
                try:
                    values = parse_values(parts, pid=int)
                    pid = values['pid']
                    comm = values['comm']
                except ValueError:
                    # perf 4
                    comm, pid = other[0].rsplit(':', 1)
                    pid = int(pid)

                # if comm != "python":
                #     if verbose >= 2:
                #         log(f'Skip waking event for {comm}')
                #     continue
                if pid not in last_sleep_time:
                    # raise ValueError(f'pid {pid} not seen sleeping before, only {last_sleep_time}')
                    # this can happen when we did not see the creation
                    # q
                    last_run_time[pid] = time
                    continue
                recover_from_gil = takes_gil(last_sleep_stacktrace[pid])
                duration = time  - last_sleep_time[pid]
                if verbose >= 2:
                    name = pid_names.get(pid, pid)
                    log(f'Waking up {name}', '(recovering from GIL)' if recover_from_gil else '', f', slept for {duration} msec')
                if verbose >= 3:
                    print("Stack trace when we went to sleep:\n\t", "\t".join(last_sleep_stacktrace[pid]))
                if store_sleeping:
                    if recover_from_gil:
                        name = 'S(GIL)'
                        cname = 'terrible'
                    else:
                        name = 'S'
                        cname = 'bad'
                    event = {"pid": parent_pid.get(pid, pid), "tid": pid, "ts": last_sleep_time[pid], "dur": duration, "name": name, "ph": "X", "cat": "process state", 'cname': cname}
                    trace_events.append(event)
                last_run_time[pid] = time
                del last_sleep_time[pid]
            elif event == "sched:sched_process_exec":
                if verbose >= 2:
                    name = pid_names.get(triggerpid, triggerpid)
                    log(f'Starting (exec) {name}')
            elif event == "sched:sched_wakeup_new":
                # e.g: swapper     0 [040] 3498299.642199:                sched:sched_waking: comm=python pid=393320 prio=120 target_cpu=040
                try:
                    values = parse_values(parts, pid=int)
                    pid = values['pid']
                except ValueError:
                    # perf 4
                    comm, pid = other[0].rsplit(':', 1)
                    pid = int(pid)
                if verbose >= 2:
                    name = pid_names.get(pid, pid)
                    log(f'Starting (new) {name}')
                last_run_time[pid] = time
            elif event == "sched:sched_process_fork":
                values = parse_values(parts, pid=int, child_pid=int)
                # set up a child parent relationship for better visualization
                pid, child_pid = values['pid'], values['child_pid']
                if verbose >= 2:
                    log(f'Process {pid} forked {child_pid}')
                parent_pid[child_pid] = pid
            elif not tracepoint:
                event = {"pid": 'counters', "ts": time, "name": event, "ph": "C", "args": {event: count}}
                trace_events.append(event)
            else:
                if verbose >= 2:
                    print("SKIP", header)
                pass
        except BrokenPipeError:
            break
        except:
            print("error on line", header, other)
            raise
            
    with open(args.output, 'w') as f:
        json.dump({'traceEvents': trace_events}, f)
    if verbose >= 1:
        print(f"Wrote to {args.output}")


if __name__ == '__main__':
    main()
