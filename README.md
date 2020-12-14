# Profiling and tracing information for Python using viztracer and perf, the GIL exposed.

This project aims to (at least demonstrate) how to combine the Linux perf tool (aka perf_events) with [viztracer](https://github.com/gaogaotiantian/viztracer) to visualize the GIL (rather process states) and various profiling statistics, or hardware performance counters.

# Installation
From PyPy

    $ pip install per4m

# Demo

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

    $ perf script --no-inline | per4m --no-running -o example1perf.json


## Step 4

Merge the viztracer and perf/per4m results into a single html file.

    $ viztracer --combine example1.json example1perf.json -o example1.html


## Step 5

Identify the problem (GIL visible, possible low instruction counts/cycle):


