import os
import tempfile
import multiprocessing
import time
import signal


def check_pid(pid):
    """Check For the existence of a unix pid."""
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    else:
        return True


def test_prefetch_crash():  # pragma: no cover
    # worker dies
    with tempfile.TemporaryDirectory() as d:
        def worker():
            with open("{}/{}".format(d, os.getpid()), "w"):
                pass
            while True:
                time.sleep(1)

        signal.signal(signal.SIGCHLD, signal.SIG_IGN)
        p = multiprocessing.Process(target=worker, daemon=False)
        p.start()

        while len(os.listdir(d)) == 0:
            time.sleep(0.05)

        os.kill(int(os.listdir(d)[0]), signal.SIGKILL)

        time.sleep(10)

        for pid in map(int, os.listdir(d)):
            assert not check_pid(pid)

test_prefetch_crash()
