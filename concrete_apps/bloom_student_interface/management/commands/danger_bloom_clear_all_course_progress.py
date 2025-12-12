from student_progress import models
from bloom_student_interface.models import Child, ChildFormProgress
import djclick as click


@click.command()
def command():
    ChildFormProgress.objects.all().delete()

    models.QuestionAnswer.objects.all().delete()
    models.FormProgress.objects.all().delete()
    models.TopicProgress.objects.all().delete()
    models.CourseProgress.objects.all().delete()
