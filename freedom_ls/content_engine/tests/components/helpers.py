"""Helpers shared by the content-widget component tests."""

from __future__ import annotations

import lxml.html

from freedom_ls.content_engine.factories import FileFactory, TopicFactory
from freedom_ls.content_engine.models import File
from freedom_ls.markdown_rendering.markdown_utils import render_markdown


def render(markup: str) -> str:
    topic = TopicFactory()
    return str(render_markdown(markup, None, context={"content_instance": topic}))


def render_tree(markup: str) -> lxml.html.HtmlElement:
    return lxml.html.fromstring(render(markup))


def audio_file(file_path: str) -> File:
    file_obj: File = FileFactory(
        file_path=file_path,
        file_type=File.FileType.AUDIO,
        mime_type="audio/mpeg",
    )
    return file_obj
