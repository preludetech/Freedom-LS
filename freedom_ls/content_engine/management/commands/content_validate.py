from pathlib import Path

import djclick as click

from freedom_ls.content_engine.ignore_list import ignore_list_for
from freedom_ls.content_engine.validate import validate


@click.command()
@click.argument("path")
def command(path):
    validate(path, ignore=ignore_list_for(Path(path)))
