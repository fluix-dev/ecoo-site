from django.core.exceptions import ValidationError
from django.db.models import Max, OuterRef, Subquery
from django.template.defaultfilters import floatformat
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy

from judge.contest_format.default import DefaultContestFormat
from judge.contest_format.registry import register_contest_format


@register_contest_format('ics3u')
class ICS3UContestFormat(DefaultContestFormat):
    name = gettext_lazy('ICS3U')

    @classmethod
    def validate(cls, config):
        if config is not None and (not isinstance(config, dict) or config):
            raise ValidationError('ICS3U contest expects no config or empty dict as config')

    def __init__(self, contest, config):
        super().__init__(contest, config)

    def update_participation(self, participation):
        score = 0
        format_data = {}

        queryset = (participation.submissions.values('problem_id')
                                             .filter(points=Subquery(
                                                 participation.submissions.filter(problem_id=OuterRef('problem_id'))
                                                                          .order_by('-points').values('points')[:1]))
                                             .annotate(disqualified=Max('is_disqualified'))
                                             .values_list('problem_id', 'disqualified', 'points'))

        for problem_id, disqualified, points in queryset:
            format_data[str(problem_id)] = {
                'points': points,
                'disqualified': disqualified,
            }
            score += points

        participation.cumtime = 0
        participation.score = score
        participation.tiebreaker = 0
        participation.format_data = format_data
        participation.save()

    def display_user_problem(self, participation, contest_problem):
        format_data = (participation.format_data or {}).get(str(contest_problem.id))
        if format_data:
            extra = ' disqualified' if format_data['disqualified'] else ''

            return format_html(
                '<td class="{state}"><a href="{url}">{points}</a></td>',
                state=self.best_solution_state(format_data['points'], contest_problem.points) + extra,
                url=reverse('contest_user_submissions',
                            args=[self.contest.key, participation.user.user.username, contest_problem.problem.code]),
                points=floatformat(format_data['points']),
            )
        else:
            return mark_safe('<td></td>')

    def display_participation_result(self, participation):
        return format_html(
            '<td class="user-points">{points}</td>',
            points=floatformat(participation.score, -self.contest.points_precision),
        )
