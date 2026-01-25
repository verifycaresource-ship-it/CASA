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
