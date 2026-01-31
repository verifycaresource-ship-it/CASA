from django.core.exceptions import PermissionDenied

def roles_required(*allowed_roles):
    """
    Decorator to restrict access to users with specific roles.
    Usage: @roles_required("admin", "finance_officer")
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not hasattr(request.user, "role") or request.user.role not in allowed_roles:
                raise PermissionDenied("You do not have permission to access this page.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

from django.shortcuts import redirect
from functools import wraps

def roles_required(*roles):
    """Allow access only to users with specific roles."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user_role = getattr(request.user, "role", None)
            if user_role not in roles:
                return redirect("/")  # or a "Permission Denied" page
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
