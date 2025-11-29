from django.core.exceptions import PermissionDenied


def roles_required(*allowed_roles):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):

            user = request.user

            if not user.is_authenticated:
                raise PermissionDenied("Authentication required")

            # Allow superusers always
            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_role = getattr(user, "role", None)

            if user_role not in allowed_roles:
                raise PermissionDenied("You do not have permission to access this page")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
