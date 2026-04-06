import django.dispatch

feedback_trigger = django.dispatch.Signal()
# Sent with: sender=<trigger_point_string>, user=<User>, context_object=<model instance>, request=<HttpRequest>
