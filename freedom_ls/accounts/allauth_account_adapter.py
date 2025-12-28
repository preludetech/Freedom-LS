from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    def is_open_for_signup(self, request):
        # return settings.ALLOW_SIGN_UPS  # TODO rather decide based on the current SITE
        return True
