import json
from datetime import datetime

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, PasswordChangeView, redirect_to_login
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Max, Min
from django.db.models.fields import DateField
from django.db.models.functions import Cast, ExtractYear
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _, gettext_lazy
from django.views.generic import DetailView, ListView, TemplateView
from reversion import revisions

from judge.forms import CustomAuthenticationForm, ProfileForm
from judge.models import Profile, Rating, Submission, Ticket
from judge.utils.problems import contest_completed_ids, user_completed_ids
from judge.utils.pwned import PwnedPasswordsValidator
from judge.utils.views import DiggPaginatorMixin, TitleMixin, generic_message
from .contests import ContestRanking

__all__ = ['UserPage', 'UserAboutPage', 'UserList', 'UserDashboard', 'users', 'edit_profile']


def remap_keys(iterable, mapping):
    return [dict((mapping.get(k, k), v) for k, v in item.items()) for item in iterable]


class UserMixin(object):
    model = Profile
    slug_field = 'user__username'
    slug_url_kwarg = 'user'
    context_object_name = 'user'

    def render_to_response(self, context, **response_kwargs):
        return super(UserMixin, self).render_to_response(context, **response_kwargs)


class UserPage(TitleMixin, UserMixin, DetailView):
    template_name = 'user/user-base.html'

    def get_object(self, queryset=None):
        if self.kwargs.get(self.slug_url_kwarg, None) is None:
            return self.request.profile
        return super(UserPage, self).get_object(queryset)

    def dispatch(self, request, *args, **kwargs):
        if self.kwargs.get(self.slug_url_kwarg, None) is None:
            if not self.request.user.is_authenticated:
                return redirect_to_login(self.request.get_full_path())
        try:
            return super(UserPage, self).dispatch(request, *args, **kwargs)
        except Http404:
            return generic_message(request, _('No such user'), _('No user handle "%s".') %
                                   self.kwargs.get(self.slug_url_kwarg, None))

    def get_title(self):
        return (_('My account') if self.request.user == self.object.user else
                _('User %s') % self.object.user.username)

    # TODO: the same code exists in problem.py, maybe move to problems.py?
    @cached_property
    def profile(self):
        if not self.request.user.is_authenticated:
            return None
        return self.request.profile

    @cached_property
    def in_contest(self):
        return self.profile is not None and self.profile.current_contest is not None

    def get_completed_problems(self):
        if self.in_contest:
            return contest_completed_ids(self.profile.current_contest)
        else:
            return user_completed_ids(self.profile) if self.profile is not None else ()

    def get_context_data(self, **kwargs):
        context = super(UserPage, self).get_context_data(**kwargs)

        context['hide_solved'] = int(self.hide_solved)
        context['authored'] = self.object.authored_problems.filter(is_public=True) \
                                  .order_by('code')
        rating = self.object.ratings.order_by('-contest__end_time')[:1]
        context['rating'] = rating[0] if rating else None

        context['rank'] = Profile.objects.filter(is_unlisted=False).count() + 1

        if rating:
            context['rating_rank'] = Profile.objects.filter(is_unlisted=False,
                                                            rating__gt=self.object.rating).count() + 1
            context['rated_users'] = Profile.objects.filter(is_unlisted=False,
                                                            rating__isnull=False).count()
        context.update(self.object.ratings.aggregate(min_rating=Min('rating'), max_rating=Max('rating'),
                                                     contests=Count('contest')))
        return context

    def get(self, request, *args, **kwargs):
        self.hide_solved = request.GET.get('hide_solved') == '1' if 'hide_solved' in request.GET else False
        return super(UserPage, self).get(request, *args, **kwargs)


class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    extra_context = {'title': _('Login')}
    authentication_form = CustomAuthenticationForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        password = form.cleaned_data['password']
        validator = PwnedPasswordsValidator()
        try:
            validator.validate(password)
        except ValidationError:
            self.request.session['password_pwned'] = True
        else:
            self.request.session['password_pwned'] = False
        return super().form_valid(form)


class CustomPasswordChangeView(PasswordChangeView):
    template_name = 'registration/password_change_form.html'

    def form_valid(self, form):
        self.request.session['password_pwned'] = False
        return super().form_valid(form)


EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


class UserDashboard(UserPage):
    template_name = 'user/user-dashboard.html'

    def get_title(self):
        return _('Dashboard')

    def get_context_data(self, **kwargs):
        user = self.request.user
        profile = self.request.profile
        context = super(UserDashboard, self).get_context_data(**kwargs)
        context['recently_attempted_problems'] = (Submission.objects.filter(user=profile, problem__is_public=True)
                                                  .exclude(problem_id__in=user_completed_ids(profile))
                                                  .values_list('problem__code', 'problem__name', 'problem__points')
                                                  .annotate(points=Max('points'), latest=Max('date'))
                                                  .order_by('-latest')
                                                  [:settings.DMOJ_BLOG_RECENTLY_ATTEMPTED_PROBLEMS_COUNT])
        context['own_tickets'] = Ticket.tickets_list(user).filter(user=profile)[:10]

        return context


class UserAboutPage(UserPage):
    template_name = 'user/user-about.html'

    def get_context_data(self, **kwargs):
        context = super(UserAboutPage, self).get_context_data(**kwargs)
        ratings = context['ratings'] = self.object.ratings.order_by('-contest__end_time').select_related('contest') \
            .defer('contest__description')

        context['rating_data'] = mark_safe(json.dumps([{
            'label': rating.contest.name,
            'rating': rating.rating,
            'ranking': rating.rank,
            'link': '%s#!%s' % (reverse('contest_ranking', args=(rating.contest.key,)), self.object.user.username),
            'timestamp': (rating.contest.end_time - EPOCH).total_seconds() * 1000,
            'date': date_format(rating.contest.end_time, _('M j, Y, G:i')),
            'class': rating_class(rating.rating),
            'height': '%.3fem' % rating_progress(rating.rating),
        } for rating in ratings]))

        if ratings:
            user_data = self.object.ratings.aggregate(Min('rating'), Max('rating'))
            global_data = Rating.objects.aggregate(Min('rating'), Max('rating'))
            min_ever, max_ever = global_data['rating__min'], global_data['rating__max']
            min_user, max_user = user_data['rating__min'], user_data['rating__max']
            delta = max_user - min_user
            ratio = (max_ever - max_user) / (max_ever - min_ever) if max_ever != min_ever else 1.0
            context['max_graph'] = max_user + ratio * delta
            context['min_graph'] = min_user + ratio * delta - delta

        submissions = (
            self.object.submission_set
            .annotate(date_only=Cast('date', DateField()))
            .values('date_only').annotate(cnt=Count('id'))
        )

        context['submission_data'] = mark_safe(json.dumps({
            date_counts['date_only'].isoformat(): date_counts['cnt'] for date_counts in submissions
        }))
        context['submission_metadata'] = mark_safe(json.dumps({
            'min_year': (
                self.object.submission_set
                .annotate(year_only=ExtractYear('date'))
                .aggregate(min_year=Min('year_only'))['min_year']
            ),
        }))
        return context


@login_required
def edit_profile(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.profile, user=request.user)
        if form.is_valid():
            with transaction.atomic(), revisions.create_revision():
                form.save()
                revisions.set_user(request.user)
                revisions.set_comment(_('Updated on site'))

            return HttpResponseRedirect(request.path)
    else:
        form = ProfileForm(instance=request.profile)

    tzmap = settings.TIMEZONE_MAP
    return render(request, 'user/edit-profile.html', {
        'form': form, 'title': _('Edit profile'), 'profile': request.profile,
        'has_math_config': bool(settings.MATHOID_URL),
        'ignore_user_script': True,
        'TIMEZONE_MAP': tzmap or 'http://momentjs.com/static/img/world.png',
        'TIMEZONE_BG': settings.TIMEZONE_BG if tzmap else '#4E7CAD',
    })


class UserList(DiggPaginatorMixin, TitleMixin, ListView):
    model = Profile
    title = gettext_lazy('Leaderboard')
    context_object_name = 'users'
    template_name = 'user/list.html'
    paginate_by = 100

    def get_queryset(self):
        return (Profile.objects.filter(is_unlisted=False)
                .order_by('id').select_related('user')
                .only('display_rank', 'user__username', 'user__first_name', 'user__last_name'))

    def get_context_data(self, **kwargs):
        context = super(UserList, self).get_context_data(**kwargs)
        context['rank_header'] = _('Id')
        context['users'] = list(map(lambda user: (user.id, user), context['users']))
        context['first_page_href'] = '.'
        return context


user_list_view = UserList.as_view()


class FixedContestRanking(ContestRanking):
    contest = None

    def get_object(self, queryset=None):
        return self.contest


def users(request):
    if request.user.is_authenticated:
        participation = request.profile.current_contest
        if participation is not None:
            contest = participation.contest
            return FixedContestRanking.as_view(contest=contest)(request, contest=contest.key)
    return user_list_view(request)


def user_ranking_redirect(request):
    try:
        username = request.GET['handle']
    except KeyError:
        raise Http404()
    user = get_object_or_404(Profile, user__username=username)
    rank = Profile.objects.filter(is_unlisted=False).count()
    rank += Profile.objects.filter(is_unlisted=False, id__lt=user.id).count()
    page = rank // UserList.paginate_by
    return HttpResponseRedirect('%s%s#!%s' % (reverse('user_list'), '?page=%d' % (page + 1) if page else '', username))


class UserLogoutView(TitleMixin, TemplateView):
    template_name = 'registration/logout.html'
    title = 'You have been successfully logged out.'

    def post(self, request, *args, **kwargs):
        auth_logout(request)
        return HttpResponseRedirect(request.get_full_path())
