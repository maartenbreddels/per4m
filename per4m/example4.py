import time

values = [('foo', 3), ('bar', 42), ('bazz', 2)]

def key_function(item):
    time.sleep(0.01)
    name, index = item
    return index

def do_sort():
    values.sort(key=key_function)
do_sort()
def do_print():
    print(values)
do_print()
