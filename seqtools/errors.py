import inspect
import threading


class EvaluationError(Exception):
    """Raised when evaluating an element fails."""


# Settings --------------------------------------------------------------------

def seterr(evaluation=None):
    """Set how errors are handled.

    Args:
        evaluation (str): how errors from user code triggered by SeqTools are
            propagated:

            - `'wrap'`: raise :class:`EvaluationError` with original error as
              its cause.
            - `'passthrough'`: let the error propagate through SeqTool code,
              might facilitate step-by-step debugging.
            - `None` leave unchanged and return current setting
    Returns:
        The setting value.
    """
    if evaluation == 'wrap':
        error_config.passthrough = False
    elif evaluation == 'passthrough':
        error_config.passthrough = True
    elif evaluation is not None:
        raise ValueError("evaluation must be 'wrap' or 'passthrough'")

    return "passthrough" if error_config.passthrough else 'wrap'


class ErrorConfig(threading.local):
    def __init__(self):
        super().__init__()
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
