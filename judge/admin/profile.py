from django.contrib import admin
from django.forms import ModelForm
from django.urls import reverse_lazy
from django.utils.html import format_html
from django.utils.translation import gettext, gettext_lazy as _, ungettext
from reversion.admin import VersionAdmin

from django_ace import AceWidget
from judge.models import Profile
from judge.utils.views import NoBatchDeleteMixin
from judge.widgets import AdminMartorWidget, AdminSelect2Widget


class ProfileForm(ModelForm):
    def __init__(self, *args, **kwargs):
        super(ProfileForm, self).__init__(*args, **kwargs)
        if 'current_contest' in self.base_fields:
            # form.fields['current_contest'] does not exist when the user has only view permission on the model.
            self.fields['current_contest'].queryset = self.instance.contest_history.select_related('contest') \
                .only('contest__name', 'user_id', 'virtual')
            self.fields['current_contest'].label_from_instance = \
                lambda obj: '%s v%d' % (obj.contest.name, obj.virtual) if obj.virtual else obj.contest.name

    class Meta:
        widgets = {
            'timezone': AdminSelect2Widget,
            'language': AdminSelect2Widget,
            'ace_theme': AdminSelect2Widget,
            'current_contest': AdminSelect2Widget,
        }


class TimezoneFilter(admin.SimpleListFilter):
    title = _('timezone')
    parameter_name = 'timezone'

    def lookups(self, request, model_admin):
        return Profile.objects.values_list('timezone', 'timezone').distinct().order_by('timezone')

    def queryset(self, request, queryset):
        if self.value() is None:
            return queryset
        return queryset.filter(timezone=self.value())


class ProfileAdmin(NoBatchDeleteMixin, VersionAdmin):
    form = ProfileForm
    fieldsets = (
        (None, {'fields': ('user', 'display_rank')}),
        (_('User Settings'), {'fields': ('timezone', 'language', 'ace_theme', 'math_engine')}),
        (_('Administration'), {'fields': ('is_unlisted',
                                          'last_access', 'ip', 'current_contest', 'notes')}),
    )
    list_display = ('user', 'full_name', 'email',
                    'date_joined', 'last_access', 'ip', 'show_public')
    ordering = ('user__username',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'ip', 'user__email')
    list_filter = ('language', TimezoneFilter)
    actions_on_top = True
    actions_on_bottom = True

    def get_queryset(self, request):
        return super(ProfileAdmin, self).get_queryset(request).select_related('user')

    def show_public(self, obj):
        return format_html('<a href="{0}" style="white-space:nowrap;">{1}</a>',
                           obj.get_absolute_url(), gettext('View on site'))
    show_public.short_description = ''

    def admin_user_admin(self, obj):
        return obj.username
    admin_user_admin.admin_order_field = 'user__username'
    admin_user_admin.short_description = _('User')

    def full_name(self, obj):
        return obj.user.get_full_name()
    full_name.short_description = _('Name')

    def email(self, obj):
        return obj.user.email
    email.admin_order_field = 'user__email'
    email.short_description = _('Email')

    def timezone_full(self, obj):
        return obj.timezone
    timezone_full.admin_order_field = 'timezone'
    timezone_full.short_description = _('Timezone')

    def date_joined(self, obj):
        return obj.user.date_joined
    date_joined.admin_order_field = 'user__date_joined'
    date_joined.short_description = _('date joined')

    def get_form(self, request, obj=None, **kwargs):
        form = super(ProfileAdmin, self).get_form(request, obj, **kwargs)
        if 'user_script' in form.base_fields:
            # form.base_fields['user_script'] does not exist when the user has only view permission on the model.
            form.base_fields['user_script'].widget = AceWidget('javascript', request.profile.ace_theme)
        return form
