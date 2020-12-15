import os
import sys

usage = """usage per4m [-h] {perf2trace,...}

optional arguments:
  -h, --help          show this help message and exit

positional arguments:
    perf2trace          convert perf.data to TraceEvent json data
    giltracer           Run VizTracer and perf, and merge the result to see where the GIL is active.

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
        main([os.path.basename(args[0]) + " " + args[1]] + args[2:])
    else:
        print(usage)
        sys.exit(0)


if __name__ == '__main__':
    main()
