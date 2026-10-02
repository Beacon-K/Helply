from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*roles):
    """Restrict a view to users holding one of the given roles."""

    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)

        return wrapper

    return decorator


def agent_required(view):
    from .models import User

    return role_required(User.Role.TECHNICIAN, User.Role.SUPERVISOR)(view)
