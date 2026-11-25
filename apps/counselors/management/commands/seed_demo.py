"""
Seed demo counsellors (with weekday availability), campus offices and library resources.

    python manage.py seed_demo --password "<choose one>"

Safe to re-run (idempotent). Counsellor accounts are created with the password you pass, or a
random one that is printed once. Refuses to run with DEBUG off unless --force is given, so demo
accounts don't get created in production by accident.
"""
import secrets
from datetime import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.counselors.models import CounselorProfile, CounselorAvailabilitySlot
from apps.library.models import Resource
from apps.referrals.models import CampusResource
from apps.users.models import CustomUser

COUNSELLORS = [
    ('amara.osei', 'Amara', 'Osei', 'Clinical Psychologist', ['Academic stress', 'Anxiety'], ['en', 'tw'], 9),
    ('alicia.lucy', 'Alicia', 'Lucy', 'Licensed Counsellor', ['Identity', 'Cultural transitions'], ['en', 'ig'], 6),
    ('david.kamau', 'David', 'Kamau', 'Student Wellness Advisor', ['Depression', 'Resilience'], ['en', 'sw'], 7),
    ('nadia.bouali', 'Nadia', 'Bouali', 'Psychotherapist', ['Trauma', 'Recovery'], ['en', 'fr'], 11),
    ('ama.asante', 'Ama', 'Asante', 'Counselling Psychologist', ['Relationships', 'Communication'], ['en', 'tw'], 5),
]

CAMPUS = [
    ('', 'guidance', 'University guidance & counselling office', 'Walk-in or by appointment on campus.'),
    ('', 'academic', 'Academic advisor', 'Course load, deferrals, and exam concerns.'),
    ('', 'career', 'Career services', 'CV help, internships, and career direction.'),
    ('', 'finance', 'Student finance office', 'Fees, bursaries, and emergency funds.'),
    ('', 'health', 'Campus health clinic', 'Medical care and prescriptions.'),
]

LIBRARY = [
    ('Understanding anxiety: a guide for students', 'article', ['anxiety']),
    ('Breathing techniques for quick relief', 'article', ['anxiety', 'exams']),
    ('When sadness becomes depression', 'article', ['depression']),
    ('Healthy boundaries in friendships and romance', 'article', ['relationships']),
    ('Sleep reset: a 7-day plan', 'article', ['sleep']),
    ('What to do when you are not okay', 'article', ['crisis']),
]


WORKBOOKS = [
    ('Exam Season Survival Workbook', 'exam-season-survival-workbook.pdf', ['exams', 'anxiety'],
     'A two-week study plan and calming exercises for exam stress.'),
    ('The Identity Workbook: culture, family and self', 'identity-workbook.pdf', ['identity', 'family'],
     'Find your values and navigate between home and campus.'),
    ('Sleep Reset: a 7-day plan', 'sleep-reset-7-day-plan.pdf', ['sleep'],
     'One small change a day for better sleep.'),
    ('My Safety Plan', 'my-safety-plan.pdf', ['crisis'],
     'Fill it in while you feel okay, so it is ready when you are not.'),
]


class Command(BaseCommand):
    help = 'Create demo counsellors, campus offices and library resources.'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Password for the demo counsellor accounts')
        parser.add_argument('--force', action='store_true', help='Allow running when DEBUG is off')

    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts['force']:
            raise CommandError('DEBUG is off. Pass --force if you really want demo data here.')
        password = opts['password'] or secrets.token_urlsafe(12)
        created_accounts = 0
        for username, first, last, role, specialties, langs, years in COUNSELLORS:
            user, new = CustomUser.objects.get_or_create(
                username=username,
                defaults=dict(first_name=first, last_name=last, email=f'{username}@jalimind.demo',
                              role='counselor', consent_given=True),
            )
            if new:
                user.set_password(password)
                user.save()
                created_accounts += 1
            profile, _ = CounselorProfile.objects.get_or_create(user=user, defaults=dict(
                bio=f'{role}. Supporting university students across Africa.', specialties=specialties,
                languages=langs, years_experience=years, license_verified=True, is_available=True,
            ))
            for day in range(0, 5):  # Mon-Fri 09:00-13:00 and 14:00-17:00
                CounselorAvailabilitySlot.objects.get_or_create(
                    counselor=profile, day_of_week=day, start_time=time(9, 0), defaults=dict(end_time=time(13, 0)))
                CounselorAvailabilitySlot.objects.get_or_create(
                    counselor=profile, day_of_week=day, start_time=time(14, 0), defaults=dict(end_time=time(17, 0)))
        for uni, cat, name, desc in CAMPUS:
            CampusResource.objects.get_or_create(university=uni, category=cat, name=name, defaults=dict(description=desc))
        for title, kind, tags in LIBRARY:
            Resource.objects.get_or_create(title=title, defaults=dict(
                resource_type=kind, tags=tags, is_published=True, description=title))
        for title, fname, tags, desc in WORKBOOKS:
            # update_or_create so re-running after changing FRONTEND_URL fixes the links
            Resource.objects.update_or_create(title=title, defaults=dict(
                resource_type='workbook', tags=tags, is_published=True, description=desc,
                content_url=f'{settings.FRONTEND_URL}/workbooks/{fname}'))
        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(COUNSELLORS)} counsellors, {len(CAMPUS)} campus offices, '
            f'{len(LIBRARY)} articles, {len(WORKBOOKS)} workbooks.'))
        if created_accounts and not opts['password']:
            self.stdout.write(f'Counsellor password (shown once): {password}')
