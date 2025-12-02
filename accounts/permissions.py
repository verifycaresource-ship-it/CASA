from rest_framework.permissions import BasePermission

class IsAdminOrAgent(BasePermission):
    """
    Allows access only to Admins or Agents.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'agent']

class IsAdminOrClaimOfficer(BasePermission):
    """
    Allows access only to Admins or Claim Officers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'claim_officer']

class IsAdminOrFinanceOfficer(BasePermission):
    """
    Allows access only to Admins or Finance Officers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'finance_officer']

class IsAdminOrReportOfficer(BasePermission):
    """
    Allows access only to Admins or Report Officers.
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['admin', 'report_officer']
