"""Keep the original Excel server's log in the run's writable scratch."""
import logging
import tempfile
from pathlib import Path


class ScratchFileHandler(logging.FileHandler):

    def __init__(self, filename, *args, **kwargs):
        if Path(filename).name == 'excel-mcp.log':
            filename = Path(tempfile.gettempdir()) / 'excel-mcp.log'
        super().__init__(filename, *args, **kwargs)


logging.FileHandler = ScratchFileHandler
