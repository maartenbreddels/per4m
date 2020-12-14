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
