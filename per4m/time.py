import os
import time

def timed(f):
    def execute(*args, **kwargs):
        t0 = time.time()
        utime0, stime0, child_utime0, child_stime0, walltime0 = os.times()
        try:
            return f(*args, **kwargs)

        finally:
            dt = time.time() - t0
            utime, stime, child_utime, child_stime, walltime = os.times()
            # name = f.func_name
            print()
            print("user time:            % 9.3f sec." % (utime - utime0))
            print("system time:          % 9.3f sec." % (stime - stime0))
            print("user time(children):  % 9.3f sec." % (child_utime - child_utime0))
            print("system time(children):% 9.3f sec." % (child_stime - child_stime0))
            print()
            dt_total = child_utime - child_utime0 + child_stime - child_stime0 + utime - utime0 + stime - stime0
            print("total cpu time:       % 9.3f sec. (time it would take on a single cpu/core)" % (dt_total))
            print("elapsed time:         % 9.3f sec. (normal wallclock time it took)" % (walltime - walltime0))
            dt = walltime - walltime0
            if dt == 0:
                eff = 0.
            else:
                eff = dt_total / (dt)
            print("efficiency factor     % 9.3f      (ratio of the two above ~= # cores)" % eff)
    return execute
