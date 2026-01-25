from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied

def roles_required(*allowed_roles):
    """
    Decorator for views that checks if the user has one of the allowed roles.
    Usage:
        @roles_required('admin', 'agent')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if hasattr(request.user, 'role') and request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to access this page.")
        return _wrapped_view
    return decorator
