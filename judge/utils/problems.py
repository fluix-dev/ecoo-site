from collections import defaultdict
from math import e

from django.core.cache import cache
from django.db.models import Case, Count, ExpressionWrapper, F, Max, When
from django.db.models.fields import FloatField
from django.utils import timezone
from django.utils.translation import gettext as _, gettext_noop

from judge.models import Problem, Submission

__all__ = ['contest_completed_ids', 'get_result_data', 'user_completed_ids', 'user_editable_ids', 'user_tester_ids']


def user_tester_ids(profile):
    return set(Problem.objects.filter(testers=profile).values_list('id', flat=True))


def user_editable_ids(profile):
    return set(Problem.get_editable_problems(profile.user).values_list('id', flat=True))


def contest_completed_ids(participation):
    key = 'contest_complete:%d' % participation.id
    result = cache.get(key)
    if result is None:
        result = set(participation.submissions.filter(submission__result='AC', points=F('problem__points'))
                     .values_list('problem__problem__id', flat=True).distinct())
        cache.set(key, result, 86400)
    return result


def user_completed_ids(profile):
    key = 'user_complete:%d' % profile.id
    result = cache.get(key)
    if result is None:
        result = set(Submission.objects.filter(user=profile, result='AC', points=F('problem__points'))
                     .values_list('problem_id', flat=True).distinct())
        cache.set(key, result, 86400)
    return result


def contest_attempted_ids(participation):
    key = 'contest_attempted:%s' % participation.id
    result = cache.get(key)
    if result is None:
        result = {id: {'achieved_points': points, 'max_points': max_points}
                  for id, max_points, points in (participation.submissions
                                                 .values_list('problem__problem__id', 'problem__points')
                                                 .annotate(points=Max('points'))
                                                 .filter(points__lt=F('problem__points')))}
        cache.set(key, result, 86400)
    return result


def user_attempted_ids(profile):
    key = 'user_attempted:%s' % profile.id
    result = cache.get(key)
    if result is None:
        result = {id: {'achieved_points': points, 'max_points': max_points}
                  for id, max_points, points in (Submission.objects.filter(user=profile)
                                                 .values_list('problem__id', 'problem__points')
                                                 .annotate(points=Max('points'))
                                                 .filter(points__lt=F('problem__points')))}
        cache.set(key, result, 86400)
    return result


def _get_result_data(results):
    return {
        'categories': [
            # Using gettext_noop here since this will be tacked into the cache, so it must be language neutral.
            # The caller, SubmissionList.get_result_data will run ugettext on the name.
            {'code': 'AC', 'name': gettext_noop('Accepted'), 'count': results['AC']},
            {'code': 'WA', 'name': gettext_noop('Wrong'), 'count': results['WA']},
            {'code': 'CE', 'name': gettext_noop('Compile Error'), 'count': results['CE']},
            {'code': 'TLE', 'name': gettext_noop('Timeout'), 'count': results['TLE']},
            {'code': 'ERR', 'name': gettext_noop('Error'),
             'count': results['MLE'] + results['OLE'] + results['IR'] + results['RTE'] + results['AB'] + results['IE']},
        ],
        'total': sum(results.values()),
    }


def get_result_data(*args, **kwargs):
    if args:
        submissions = args[0]
        if kwargs:
            raise ValueError(_("Can't pass both queryset and keyword filters"))
    else:
        submissions = Submission.objects.filter(**kwargs) if kwargs is not None else Submission.objects
    raw = submissions.values('result').annotate(count=Count('result')).values_list('result', 'count')
    return _get_result_data(defaultdict(int, raw))
