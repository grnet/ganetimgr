""" Supports preview. """
from django.shortcuts import render

from . import md_settings


def preview(request):
    """ Render preview page.

    :returns: A rendered preview

    """
    if md_settings.MARKDOWN_PROTECT_PREVIEW:
        user = getattr(request, 'user', None)
        if user and not user.is_staff:
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(request.get_full_path())

    return render(
        request, md_settings.MARKDOWN_PREVIEW_TEMPLATE, dict(
            content=request.REQUEST.get('data', 'No content posted'),
            css=md_settings.STATIC_URL + md_settings.MARKDOWN_STYLE,
        ))
