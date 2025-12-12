from django.urls import reverse


def bloom(request):
    # view_name = request.resolver_match.view_name
    return {
        "navigation": [
            {
                "title": "My Children",
                "url": reverse("bloom_student_interface:children"),
            },
            {"title": "My Learning", "url": reverse("bloom_student_interface:learn")},
        ]
    }
