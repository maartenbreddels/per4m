# Profiling and tracing information for Python using viztracer and perf, the GIL exposed.

This project aims to (at least demonstrate) how to combine the Linux perf tool (aka perf_events) with [viztracer](https://github.com/gaogaotiantian/viztracer) to visualize the GIL (rather process states) and various profiling statistics, or hardware performance counters.

# Installation
## Python side
From PyPy

    $ pip install per4m


## Linux side

Install perf

    $ sudo yum install perf

Enable users to run perf (use at own risk)

    $ sudo sysctl kernel.perf_event_paranoid=-1

Enable users to see schedule trace events:

    $ sudo mount -o remount,mode=755 /sys/kernel/debug
    $ sudo mount -o remount,mode=755 /sys/kernel/debug/tracing

# Usage

    $ per4m giltracer -m per4m.example2

Open the result.html, and identify the problem (GIL visible, possible low instruction counts/cycle):


![image](https://user-images.githubusercontent.com/1765949/102187104-db0c0c00-3eb3-11eb-93ef-e6d938d9e349.png)


The dark red `S(GIL)` blocks indicate the threads/processes are in a waiting state due to the GIL, dark orange `S` is a due to other reasons (like `time.sleep(...)`). The regular pattern is due to Python switching threads after [`sys.getswitchinterval`](https://docs.python.org/3/library/sys.html#sys.getswitchinterval) (0.005 seconds)

# Usage - Jupyter notebook

First, load the magics
```
%load_ext per4m.cellmagic
```

Run a cell with the `%%giltrace` cell magic.
```
%%giltrace
import threading
import time
import time


def run():
    total = 0
    for i in range(1_000_000):
        total += i
    return total


thread1 = threading.Thread(target=run)
thread2 = threading.Thread(target=run)
thread1.start()
thread2.start()
time.sleep(0.2)
for thread in [thread1, thread2]:
    thread.join()
```
Output:
```
Saving report to /tmp/tmp2rwf1xq3/viztracer.json ...
Dumping trace data to json, total entries: 89, estimated json file size: 10.4KiB
Report saved.

[ perf record: Woken up 8 times to write data ]
[ perf record: Captured and wrote 2,752 MB /tmp/tmp2rwf1xq3/perf.data (415 samples) ]

Wait for perf to finish...
Saving report to /home/maartenbreddels/github/maartenbreddels/per4m/result.html ...
Dumping trace data to json, total entries: 167, estimated json file size: 19.6KiB
Generating HTML report
Report saved.
Download result.html
Open result.html in new tab (might not work due to security issue)
```

Click the download link to get the results.

# Usage - manual

## Step 1
Create a script that uses viztracer to store trace information:

```python[example1.py]
import threading
import time
import viztracer
import time


def run():
    total = 0
    for i in range(1_000_000):
        total += i
    return total


with viztracer.VizTracer(output_file="example1.json"):
    thread1 = threading.Thread(target=run)
    thread2 = threading.Thread(target=run)
    thread1.start()
    thread2.start()
    time.sleep(0.2)
    for thread in [thread1, thread2]:
        thread.join()

```

## Step 2
Run and trace scheduler events from the kernel (to capture GIL information) and measure hardware performance counters

```
$ perf record -e 'sched:*' --call-graph dwarf -k CLOCK_MONOTONIC -e L1-dcache-load-misses -e instructions -e cycles -e page-faults -- python -m per4m.example1
Loading finish
Saving report to /home/maartenbreddels/github/maartenbreddels/per4m/example1.json ...
Dumping trace data to json, total entries: 76, estimated json file size: 8.9KiB
Report saved.
[ perf record: Woken up 139 times to write data ]
[ perf record: Captured and wrote 26,139 MB perf.data (3302 samples) ]
```

## Step 3
Convert `perf.data` to [Trace Event Format](https://docs.google.com/document/d/1CvAClvFfyA5R-PhYUmn5OOQtYMH4h6I0nSsKchNAySU/)

    $ perf script --no-inline | per4m perf2trace --no-running -o example1perf.json


## Step 4

Merge the viztracer and perf/per4m results into a single html file.

    $ viztracer --combine example1.json example1perf.json -o example1.html



## GIL load vs GIL wait

Even though a thread may have a lock on the GIL, if other don't need it, it's fine. For instance, using [gil_load](https://github.com/chrisjbillington/gil_load):
```
$ python -m gil_load per4m/example3.py
eld: 1.0 (1.0, 1.0, 1.0)
wait: 0.083 (0.083, 0.083, 0.083)
  <139967101757248>
    held: 1.0 (1.0, 1.0, 1.0)
    wait: 0.0 (0.0, 0.0, 0.0)
  <139957774272256>
    held: 0.0 (0.0, 0.0, 0.0)
    wait: 0.083 (0.083, 0.083, 0.083)
  <139957765879552>
    held: 0.0 (0.0, 0.0, 0.0)
    wait: 0.083 (0.083, 0.083, 0.083)
```
Show one thread that has a high GIL load, but it does not keep the others from running (except 8% of the time), i.e. wait is low (see [example3.py](https://github.com/maartenbreddels/per4m/blob/master/per4m/example3.py)). We can visualize this using `giltracer` (not that we import numpy and some other modules before tracing to avoid clutter)

    $ per4m giltracer --import="numpy,threading,time,gil_load" -m per4m.example3

![image](https://user-images.githubusercontent.com/1765949/102223915-96996400-3ee5-11eb-9e2e-46ac6fd5c5e3.png)
