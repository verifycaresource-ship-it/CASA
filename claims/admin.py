from django.contrib import admin
from .models import Claim

@admin.register(Claim)
class ClaimAdmin(admin.ModelAdmin):
    list_display = ('claim_number', 'client', 'policy', 'hospital', 'amount', 'status', 'created_at')
    list_filter = ('status', 'hospital', 'created_at')
    search_fields = ('claim_number', 'client__first_name', 'client__last_name')
    actions = ['approve_claims', 'reject_claims']

    @admin.action(description='Approve selected claims')
    def approve_claims(self, request, queryset):
        queryset.update(status='approved')

    @admin.action(description='Reject selected claims')
    def reject_claims(self, request, queryset):
        queryset.update(status='rejected')
