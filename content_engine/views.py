from django.shortcuts import render, get_object_or_404
from .models import Topic


def topic_detail(request, pk):
    """Simple view to display a topic."""
    topic = get_object_or_404(Topic, pk=pk)
    return render(request, 'content_engine/topic_detail.html', {'topic': topic})
