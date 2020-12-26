# Sanity checks before making a release

import os
import subprocess

import pkg_resources
import pytest


def check_output(cmd):
    try:
        out = subprocess.check_output(
            cmd.split(),
            cwd=os.path.dirname(os.path.dirname(__file__)),
            stderr=subprocess.STDOUT,
            universal_newlines=True)
    except subprocess.CalledProcessError:
        return None
    else:
        return out.rstrip()


def candidate_for_release():
    if check_output("git rev-parse --abbrev-ref HEAD") != "master":
        return False

    if check_output("git describe --exact-match --tags") is None:
        return False

    return True


if not candidate_for_release():
    pytest.skip("skipping pre-release tests (not a release)",
                allow_module_level=True)


def test_version():
    version = pkg_resources.require("seqtools")[0].version

    tag = check_output("git describe --exact-match --tags").lstrip('v')

    assert tag == version, "Package version and commit tag do not match"
