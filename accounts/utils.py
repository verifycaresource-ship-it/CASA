from functools import wraps
from django.shortcuts import render

def roles_required(*allowed_roles):
    """
    Decorator to restrict access to users with allowed roles or superusers.
    Superusers always allowed.
    Usage:
        @roles_required("admin", "finance_officer")
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = request.user
            if user.is_authenticated and (user.is_superuser or getattr(user, "role", "") in allowed_roles):
                return view_func(request, *args, **kwargs)
            return render(request, "403.html", status=403)
        return _wrapped_view
    return decorator
