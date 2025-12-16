from django.apps import AppConfig


class BloomStudentInterfaceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'bloom_student_interface'

    def ready(self):
        import bloom_student_interface.signals  # noqa
