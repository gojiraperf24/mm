"""PlatformIO entry with a scoped Windows executable-path quoting workaround.

PlatformIO 6.1.18 joins the Python executable and a package postinstall script
without quoting the executable when a package uses a string-valued script.
The project path contains spaces. Only that exact shell-command prefix changes.
"""
import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault('PLATFORMIO_CORE_DIR',str(Path(__file__).resolve().parents[1]/'.platformio'))
original_run=subprocess.run


def quoted_run(command,*args,**kwargs):
    prefix=sys.executable+' '
    if os.name=='nt' and kwargs.get('shell') and isinstance(command,str) and command.startswith(prefix):
        command=subprocess.list2cmdline([sys.executable])+command[len(sys.executable):]
    return original_run(command,*args,**kwargs)


subprocess.run=quoted_run
from platformio.__main__ import main
main()
