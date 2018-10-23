import sys
import inspect
import threading
from future.utils import raise_with_traceback


class EvaluationError(Exception):
    """Raised when evaluating an element fails."""
    pass


# Settings --------------------------------------------------------------------

def seterr(evaluation='wrap'):
    """Set how errors are handled.

    Args:
        evaluation (str): how errors from user code triggered by SeqTools are
            propagated:

            - `'wrap'`: raise :class:`EvaluationError` with original error as
              its cause.
            - `'passthrough'`: let the error propagate through SeqTool code,
              might facilitate step-by-step debugging.
    """
    if evaluation == 'wrap':
        error_config.passthrough = False
    elif evaluation == 'passthrough':
        error_config.passthrough = True
    else:
        raise ValueError("evaluation must be 'wrap' or 'passthrough'")


def passthrough():
    return error_config.passthrough


class ErrorConfig(threading.local):
    def __init__(self):
        self.passthrough = False


error_config = ErrorConfig()


# Helpers ---------------------------------------------------------------------

def unindent(lines):
    if lines is None:
        return []

    prefix = lines[0]
    while len(prefix) > 0 and not prefix.isspace():
        prefix = prefix[:-1]

    for line in lines[1:]:
        while not line.startswith(prefix):
            prefix = prefix[:-1]

    return [line[len(prefix):] for line in lines]


def format_stack(skip=1):
    out = ""
    for frame in inspect.stack()[:skip:-1]:
        _, filename, lineno, function, code_context, _ = frame
        out += "  File \"{}\", line {}, in {}\n".format(
            filename, lineno, function)
        for line in unindent(code_context):
            out += "    " + line

    return out


def with_traceback(error, tb):
    if sys.version_info.major == 2:
        try:
            raise_with_traceback(error, tb)
        except Exception as error:
            return error
    else:
        return error.with_traceback(tb)
