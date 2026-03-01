import djclick as click

from freedom_ls.content_engine.validate import validate


@click.command()
@click.argument("path")
def command(path):
    validate(path)
