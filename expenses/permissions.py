"""
Custom DRF permissions for SpendWise.
Ensures strict object-level user ownership for all API operations.
"""

from rest_framework import permissions


class IsOwner(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to access or edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read or write permissions are strictly granted only to the owner
        return obj.user == request.user
