import djclick as click

from freedom_ls.form_engine import models as form_models
from freedom_ls.learner_progress import models


@click.command()
def command():
    form_models.QuestionAnswer.objects.all().delete()
    models.CourseFormAttempt.objects.all().delete()
    form_models.FormProgress.objects.all().delete()
    models.TopicProgress.objects.all().delete()
    models.CourseProgress.objects.all().delete()
