# shows high gil load, but no wait
import threading
import time
import numpy as np

# if we don't run with gil_load, we just skip it
import gil_load
try:
    gil_load.init()
    gil_load.start()
    use_gil_load = True
except RuntimeError:
    use_gil_load = False


N = 1024*1024*32
M = 4
x = np.arange(N, dtype='f8')


def some_numpy_computation():
    total = 0
    for i in range(M):
        total += x.sum()
    return total


thread1 = threading.Thread(target=some_numpy_computation)
thread2 = threading.Thread(target=some_numpy_computation)


def main(args=None):
    thread1.start()
    thread2.start()
    total = 0
    for i in range(2_000_000):
        total += i
    for thread in [thread1, thread2]:
        thread.join()

    if use_gil_load:
        gil_load.stop()
        stats = gil_load.get()
        print(gil_load.format(stats))
if __name__ == "__main__":
    main()
