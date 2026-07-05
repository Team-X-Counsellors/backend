import pytest
from rest_framework.test import APIClient
from apps.users.models import CustomUser
from apps.counselors.models import CounselorProfile


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def student_user(db):
    user = CustomUser.objects.create_user(
        username='teststudent',
        email='student@test.com',
        password='pass1234!',
        role='student',
        consent_given=True,
    )
    return user


@pytest.fixture
def counselor_user(db):
    user = CustomUser.objects.create_user(
        username='testcounselor',
        email='counselor@test.com',
        password='pass1234!',
        role='counselor',
        consent_given=True,
    )
    CounselorProfile.objects.create(user=user)
    return user


@pytest.fixture
def admin_user(db):
    return CustomUser.objects.create_user(
        username='testadmin',
        email='admin@test.com',
        password='pass1234!',
        role='admin',
        consent_given=True,
    )


@pytest.fixture
def superadmin_user(db):
    return CustomUser.objects.create_user(
        username='testsuperadmin',
        email='superadmin@test.com',
        password='pass1234!',
        role='superadmin',
        consent_given=True,
    )


@pytest.fixture
def student_client(api_client, student_user):
    api_client.force_authenticate(user=student_user)
    return api_client


@pytest.fixture
def counselor_client(api_client, counselor_user):
    api_client.force_authenticate(user=counselor_user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    return api_client
