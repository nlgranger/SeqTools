import os
import subprocess
import re


# This line is updated automatically
version = "0.8.2-r10-g9465d02"

# If we are in the repo, the following script will update the version
# number and update this file, otherwise, we are probably in the source
# distribution and the above version number is up-to-date.
thisdir = os.path.dirname(__file__)
try:
    description = subprocess.check_output(
        "git describe --tags ".split(),
        stderr=subprocess.STDOUT,
        cwd=os.path.dirname(__file__),
        universal_newlines=True)
    description = description.rstrip()

except subprocess.CalledProcessError:
    pass

else:
    parts = description.split("-")
    parts[0] = parts[0][1:]  # remove 'v' prefix

    if len(parts) == 1:  # tagged release
        version = parts[0]
    elif len(parts) == 3:  # tag + a few commits
        tag, revision, commit = parts
        version = "{}-r{}-{}".format(tag, revision, commit)
    else:
        raise RuntimeError("Invalid version format")

    thisfile = open(__file__).read()

    with open(__file__, "w") as f:
        f.write(re.sub(r"version = \".*\"\n",
                       "version = \"{}\"\n".format(version),
                       thisfile, count=1))
