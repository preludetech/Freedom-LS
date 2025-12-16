from freedom_ls.student_progress import models
import djclick as click


@click.command()
def command():
    models.QuestionAnswer.objects.all().delete()
    models.FormProgress.objects.all().delete()
    models.TopicProgress.objects.all().delete()
    models.CourseProgress.objects.all().delete()
