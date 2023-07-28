from typing import Callable, Union

class RefCountedBuffer:
    """Wrapper around buffer objects with settable callback."""

    cb: Callable = ...
    rc: int = ...
    def __init__(
        self, array: Union[bytes, bytearray, memoryview], cb: Callable
    ) -> None: ...
