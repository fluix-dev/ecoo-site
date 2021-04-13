from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from judge.models.choices import ACE_THEMES, MATH_ENGINES_CHOICES, TIMEZONE
from judge.models.runtime import Language

__all__ = ['Profile']


class Profile(models.Model):
    user = models.OneToOneField(User, verbose_name=_('user associated'), on_delete=models.CASCADE)
    timezone = models.CharField(max_length=50, verbose_name=_('location'), choices=TIMEZONE,
                                default=settings.DEFAULT_USER_TIME_ZONE)
    language = models.ForeignKey('Language', verbose_name=_('preferred language'), on_delete=models.SET_DEFAULT,
                                 default=Language.get_default_language_pk)
    problem_count = models.IntegerField(default=0, db_index=True)
    ace_theme = models.CharField(max_length=30, choices=ACE_THEMES, default='github')
    last_access = models.DateTimeField(verbose_name=_('last access time'), default=now)
    ip = models.GenericIPAddressField(verbose_name=_('last IP'), blank=True, null=True)
    display_rank = models.CharField(max_length=10, default='user', verbose_name=_('display rank'),
                                    choices=(('user', _('Normal User')),
                                             ('admin', _('Admin'))))
    is_unlisted = models.BooleanField(verbose_name=_('unlisted user'), help_text=_('User will not be ranked.'),
                                      default=False)
    current_contest = models.OneToOneField('ContestParticipation', verbose_name=_('current contest'),
                                           null=True, blank=True, related_name='+', on_delete=models.SET_NULL)
    math_engine = models.CharField(verbose_name=_('math engine'), choices=MATH_ENGINES_CHOICES, max_length=4,
                                   default=settings.MATHOID_DEFAULT_TYPE,
                                   help_text=_('the rendering engine used to render math'))
    notes = models.TextField(verbose_name=_('internal notes'), null=True, blank=True,
                             help_text=_('Notes for administrators regarding this user.'))

    @cached_property
    def username(self):
        return self.user.username

    def remove_contest(self):
        self.current_contest = None
        self.save()

    remove_contest.alters_data = True

    def update_contest(self):
        contest = self.current_contest
        if contest is not None and (contest.ended or not contest.contest.is_accessible_by(self.user)):
            self.remove_contest()

    update_contest.alters_data = True

    def get_absolute_url(self):
        return reverse('user_page', args=(self.user.username,))

    def __str__(self):
        return self.user.username

    @classmethod
    def get_user_css_class(cls, display_rank, rating=None, rating_colors=settings.DMOJ_RATING_COLORS):
        if rating_colors:
            return 'rating rate-none %s' % display_rank
        return display_rank

    @cached_property
    def css_class(self):
        return self.get_user_css_class(self.display_rank)

    class Meta:
        permissions = (
            ('view_name', _("View user's real name")),
        )
        verbose_name = _('user profile')
        verbose_name_plural = _('user profiles')
