#include <Python.h>
#include <frameobject.h>

extern "C" void pytrace_function_entry(const char *filename,
                                       const char *funcname, int lineno,
                                       int what);
extern "C" void pytrace_function_return(const char *filename,
                                        const char *funcname, int lineno,
                                        int what);

int pytrace_trace(PyObject *obj, PyFrameObject *frame, int what,
                  PyObject *arg) {
  if ((what == PyTrace_CALL) || (what == PyTrace_C_CALL)) {
    // simular to https://github.com/python/cpython/blob/master/Python/ceval.c
    // dtrace_function_entry
    const char *filename;
    const char *funcname;
    int lineno;

    PyCodeObject *code = frame->f_code;
    filename = PyUnicode_AsUTF8(code->co_filename);
    funcname = PyUnicode_AsUTF8(code->co_name);
    lineno = PyCode_Addr2Line(code, frame->f_lasti);

    pytrace_function_entry(filename, funcname, lineno, what);
  }
  if ((what == PyTrace_RETURN) || (what == PyTrace_C_RETURN)) {
    const char *filename;
    const char *funcname;
    int lineno;

    PyCodeObject *code = frame->f_code;
    filename = PyUnicode_AsUTF8(code->co_filename);
    funcname = PyUnicode_AsUTF8(code->co_name);
    lineno = PyCode_Addr2Line(code, frame->f_lasti);

    pytrace_function_return(filename, funcname, lineno, what);
  }
  return 0;
}

static PyObject *pytrace_start(PyObject *obj, PyObject *args) {
  PyEval_SetProfile(pytrace_trace, NULL);
  // PyObject *threading_module = PyImport_ImportModule("threading");
  // PyObject *threading_setprofile =
  //     PyObject_GetAttrString(threading_module, "setprofile");
  // Py_INCREF(Py_None);
  // PyObject *pytrace_cfunction = PyCFunction_New(pytrace_trace, Py_None);
  // PyObject *args = Py_BuildValue("(N)", pytrace_cfunction);
  // PyObject_CallObject(setprofile, args);
  // Py_DECREF(args);
  Py_RETURN_NONE;
}

static PyObject *pytrace_stop(PyObject *obj, PyObject *args) {
  PyEval_SetProfile(NULL, NULL);
  Py_RETURN_NONE;
}

static PyMethodDef pytrace_methods[] = {
    {"start", (PyCFunction)pytrace_start, METH_VARARGS, "start tracing"},
    {"stop", (PyCFunction)pytrace_stop, METH_VARARGS, "stop tracing"},
    {NULL, NULL, 0, NULL}};

static struct PyModuleDef pytrace_module = {
    PyModuleDef_HEAD_INIT, "per4m.pytrace", NULL, -1, pytrace_methods};

PyMODINIT_FUNC PyInit_pytrace(void) {
  PyObject *m = PyModule_Create(&pytrace_module);

  if (!m) {
    return NULL;
  }

  return m;
}