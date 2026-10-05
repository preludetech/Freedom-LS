from django.contrib.auth.models import AnonymousUser, PermissionsMixin

from freedom_ls.form_engine.models import QuestionAnswerFile


def can_download_answer_files(user: PermissionsMixin | AnonymousUser) -> bool:
    """Whether this user may download the files applicants attached.

    One permission opens both the QuestionAnswerFile admin and the download
    route, so a page never offers a download its reader cannot complete.
    """
    opts = QuestionAnswerFile._meta
    return user.has_perm(f"{opts.app_label}.view_{opts.model_name}")
