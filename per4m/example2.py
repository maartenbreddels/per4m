# same as example1, but without explicit viztracer calls
import threading
import time

# if we don't run with gil_load, we just skip it
import gil_load
try:
    gil_load.init()
    gil_load.start()
    use_gil_load = True
except RuntimeError:
    use_gil_load = False

def some_computation():
    total = 0
    for i in range(1_000_000):
        total += i
    return total


thread1 = threading.Thread(target=some_computation)
thread2 = threading.Thread(target=some_computation)
def main(args=None):
    thread1.start()
    thread2.start()
    time.sleep(0.2)
    for thread in [thread1, thread2]:
        thread.join()
    if use_gil_load:
        gil_load.stop()
        stats = gil_load.get()
        print(gil_load.format(stats))

if __name__ == "__main__":
    main()
