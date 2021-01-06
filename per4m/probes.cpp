#include <stdio.h>

extern "C" void pytrace_function_entry(const char *filename, const char *funcname, int lineno, int what) {
    // do nothing, so we can attach a probe here
}

extern "C" void pytrace_function_return(const char *filename, const char *funcname, int lineno, int what) {
    // do nothing
}