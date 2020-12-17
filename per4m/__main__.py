import os
import sys

usage = """usage per4m [-h] {perf2trace,...}

optional arguments:
  -h, --help          show this help message and exit

positional arguments:
    giltracer           Run VizTracer and perf, and merge the result to see where the GIL is active.
    offgil              Take stacktraces from VizTracer, and inject them in perf script output and print out stack traces with weights for stackcollapse.pl
    record              Run VizTracer and perf simultaneously. See also man perf record.
    script              Take stacktraces from VizTracer, and inject them in perf script output.
    perf2trace          Convert perf.data to TraceEvent JSON data.

Examples:
$ perf script --no-inline | per4m -v

"""


def main(args=sys.argv):
    if len(args) > 1 and args[1] in ["-h", "--help"]:
        print(usage)
        sys.exit(0)
    elif len(args) > 1 and args[1] == "perf2trace":
        from .perf2trace import main
        main([os.path.basename(args[0]) + " " + args[1]] + args[2:])
    elif len(args) > 1 and args[1] == "giltracer":
        from .giltracer import main
    elif len(args) > 1 and args[1] == "offgil":
        from .offgil import main
        main([os.path.basename(args[0]) + " " + args[1]] + args[2:])
    elif len(args) > 1 and args[1] == "record":
        from .record import main
        main([os.path.basename(args[0]) + " " + args[1]] + args[2:])
    elif len(args) > 1 and args[1] == "script":
        from .script import main
        main([os.path.basename(args[0]) + " " + args[1]] + args[2:])
    else:
        print(usage)
        sys.exit(0)


if __name__ == '__main__':
    main()
