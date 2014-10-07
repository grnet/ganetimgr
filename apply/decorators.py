from django.contrib.auth.decorators import user_passes_test


def any_permission_required(*args):
    def test_func(user):
        for perm in args:
            if user.has_perm(perm):
                return True
        return False
    return user_passes_test(test_func)
