#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>
#include <stddef.h>


// C Object -------------------------------------------------------------------

typedef struct {
    PyObject_HEAD
    PyObject* array;
    PyObject* cb;
    int refcount;
} RefCountedBufferObject;

// Structure containing backed-up fields of a wrapped buffer
typedef struct {
    PyObject* obj;
    void* internal;
} BufferInternals;


// Python type implementation -------------------------------------------------

static PyObject *
RefCountedBuffer_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
    RefCountedBufferObject *self;
    self = (RefCountedBufferObject *) type->tp_alloc(type, 0);
    if (self != NULL) {
        self->array = NULL;
        Py_INCREF(Py_None);
        self->cb = Py_None;
        self->refcount = 0;
    }
    return (PyObject *) self;
}

static int
RefCountedBuffer_traverse(RefCountedBufferObject *self, visitproc visit, void *arg)
{
    Py_VISIT(self->array);
    Py_VISIT(self->cb);
    return 0;
}

static int
RefCountedBuffer_clear(RefCountedBufferObject *self)
{
    Py_CLEAR(self->array);
    Py_CLEAR(self->cb);
    return 0;
}

static void
RefCountedBuffer_dealloc(RefCountedBufferObject *self)
{
    PyObject_GC_UnTrack(self);
    RefCountedBuffer_clear(self);
    Py_TYPE(self)->tp_free((PyObject *) self);
}

static int
RefCountedBuffer_getbuffer(PyObject *obj, Py_buffer *view, int flags)
{
    RefCountedBufferObject *self = (RefCountedBufferObject *) obj;

    // Sanity checks
    if (view == NULL) {
        PyErr_SetString(PyExc_ValueError, "NULL view in getbuffer");
        return -1;
    }
    if (self->array == NULL) {
        PyErr_SetString(PyExc_RuntimeError, "array field uninitialized");
        return -1;
    }

    // Create new buffer
    if (PyObject_GetBuffer(self->array, view, flags) != 0) {
        view->obj = NULL;
        return -1;
    }

    // Wrap it
    BufferInternals* internal = (BufferInternals*) malloc(sizeof(BufferInternals));
    if (internal == NULL) {
        PyErr_SetString(PyExc_MemoryError, "out of memory");
        PyBuffer_Release(view);
        view->obj = NULL;
        return -1;
    }

    internal->obj = view->obj;
    internal->internal = view->internal;
    view->obj = obj;
    view->internal = internal;

    // Update refcounts
    self->refcount++;
    Py_INCREF(self);  // need to increase the reference count

    return 0;
}

void
RefCountedBuffer_releasebuffer(PyObject* obj, Py_buffer *view)
{
    // Save the current exception, if any
    PyObject *error_type, *error_value, *error_traceback;
    PyErr_Fetch(&error_type, &error_value, &error_traceback);

    RefCountedBufferObject* self = (RefCountedBufferObject*) obj;

    // Unwrap buffer
    BufferInternals* internal = (BufferInternals*) (view->internal);
    view->obj = internal->obj;
    view->internal = internal->internal;

    // Release memory
    free(internal);
    PyBuffer_Release(view);

    // Trigger callback if needed
    self->refcount--;
    if (self->refcount == 0 && self->cb != NULL && self->cb != Py_None) {
        PyObject *arglist;
        PyObject *result;

        arglist = Py_BuildValue("(O)", obj);
        PyErr_Clear();
        result = PyObject_CallObject(self->cb, arglist);
        Py_DECREF(arglist);

        if (result == NULL) {  // callback raised, we can only print the error
            fprintf(stderr, "RefCountedBuffer encountered an error in the callback:\n");
            PyErr_Print();
        }

        Py_XDECREF(result);
    }

    // Refcount to self is decreased by PyBuffer_Release

    // Restore current exception, if any
    PyErr_Restore(error_type, error_value, error_traceback);
}


// Methods --------------------------------------------------------------------

static int
RefCountedBuffer_init(RefCountedBufferObject *self, PyObject *args, PyObject *kwds)
{
    PyObject *array = NULL, *cb = NULL, *tmp = NULL;

    // Parse arguments
    static char *kwlist[] = {"array", "cb", NULL};
    if (!PyArg_ParseTupleAndKeywords(args, kwds, "O|O", kwlist, &array, &cb)) {
        return -1;
    }

    // Check array exposes buffer interface
    if (PyObject_CheckBuffer(array) == 0) {
        PyErr_SetString(PyExc_ValueError, "array does not implement buffer protocol");
        return -1;
    }

    Py_INCREF(array);
    tmp = self->array;
    self->array = array;
    Py_XDECREF(tmp);

    cb = cb != NULL ? cb : Py_None;
    Py_INCREF(cb);
    tmp = self->cb;
    self->cb = cb;
    Py_XDECREF(tmp);

    return 0;
}


// Type registration ----------------------------------------------------------

static PyBufferProcs RefCountedBuffer_as_buffer = {
  (getbufferproc)RefCountedBuffer_getbuffer,
  (releasebufferproc)RefCountedBuffer_releasebuffer,
};


static PyMemberDef RefCountedBuffer_members[] = {
    {"cb", T_OBJECT_EX, offsetof(RefCountedBufferObject, cb), 0, "refcount 0 callback"},
    {"rc", T_INT, offsetof(RefCountedBufferObject, refcount), READONLY, "ref count"},
    {NULL}
};


static PyTypeObject RefCountedBufferType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "seqtools.C.memory.RefCountedBuffer",
    .tp_doc = "A buffer wrapper with a settable destructor hook",
    .tp_basicsize = sizeof(RefCountedBufferObject),
    .tp_itemsize = 0,
    .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
    .tp_new = RefCountedBuffer_new,
    .tp_init = (initproc) RefCountedBuffer_init,
    .tp_dealloc = (destructor) RefCountedBuffer_dealloc,
    .tp_traverse = (traverseproc) RefCountedBuffer_traverse,
    .tp_clear = (inquiry) RefCountedBuffer_clear,
    .tp_members = RefCountedBuffer_members,
    .tp_as_buffer = &RefCountedBuffer_as_buffer,
};


// Module ---------------------------------------------------------------------

static PyModuleDef memory = {
    PyModuleDef_HEAD_INIT,
    .m_name = "seqtools.C.refcountedbuffer",
    .m_doc = "Wrapper around buffer objects with settable callback.",
    .m_size = -1,
};


PyMODINIT_FUNC
PyInit_refcountedbuffer(void)
{
    PyObject *m;
    if (PyType_Ready(&RefCountedBufferType) < 0)
        return NULL;

    m = PyModule_Create(&memory);
    if (m == NULL)
        return NULL;

    Py_INCREF(&RefCountedBufferType);
    if (PyModule_AddObject(m, "RefCountedBuffer", (PyObject *) &RefCountedBufferType) < 0) {
        Py_DECREF(&RefCountedBufferType);
        Py_DECREF(m);
        return NULL;
    }

    return m;
}
