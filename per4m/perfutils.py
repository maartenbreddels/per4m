def read_events(input):
    first_line = True
    stacktrace = []
    header = None
    for line in input:
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
    if stacktrace:
        yield header, stacktrace


def parse_header(header):
    parts = header.split()
    event = parts[4][:-1] # strip off ':'
    if ":" in event:  # tracepoint
        dso, triggerpid, cpu, time, _, *other = parts
        time = float(time[:-1]) * 1e6
        values = dict(dso=dso, triggerpid=int(triggerpid), cpu=cpu, time=time)
        tracepoint = True
    else:  # counter etc
        dso, triggerpid, time, count, _, *other = parts
        time = float(time[:-1]) * 1e6
        values = dict(dso=dso, triggerpid=int(triggerpid), count=count, time=time)
        tracepoint = False
    return values, other, tracepoint
