from freedom_ls.content_engine.validate import validate

import djclick as click

@click.command()
@click.argument('path')
def command(path):
    validate(path)
    