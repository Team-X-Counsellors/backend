import pytest
from rest_framework.test import APIClient
from apps.users.models import CustomUser


@pytest.mark.django_db
class TestRegistration:
    def test_register_student_success(self, api_client):
        res = api_client.post('/api/auth/register/', {
            'username': 'newstudent',
            'email': 'new@test.com',
            'password': 'securepass123!',
            'password_confirm': 'securepass123!',
            'role': 'student',
            'consent_given': True,
        })
        assert res.status_code == 201
        assert 'access' in res.data
        assert res.data['user']['role'] == 'student'

    def test_register_without_consent_fails(self, api_client):
        res = api_client.post('/api/auth/register/', {
            'username': 'badstudent',
            'email': 'bad@test.com',
            'password': 'securepass123!',
            'password_confirm': 'securepass123!',
            'consent_given': False,
        })
        assert res.status_code == 400

    def test_register_password_mismatch_fails(self, api_client):
        res = api_client.post('/api/auth/register/', {
            'username': 'mismatch',
            'email': 'mis@test.com',
            'password': 'securepass123!',
            'password_confirm': 'differentpass!',
            'consent_given': True,
        })
        assert res.status_code == 400


@pytest.mark.django_db
class TestRoleEnforcement:
    def test_student_cannot_access_admin_reports(self, student_client):
        res = student_client.get('/api/admin/reports/utilization/')
        assert res.status_code == 403

    def test_counselor_cannot_access_admin_reports(self, counselor_client):
        res = counselor_client.get('/api/admin/reports/utilization/')
        assert res.status_code == 403

    def test_admin_can_access_admin_reports(self, admin_client):
        res = admin_client.get('/api/admin/reports/utilization/')
        assert res.status_code == 200

    def test_student_cannot_access_counselor_profile_manage(self, student_client):
        res = student_client.get('/api/counselors/me/')
        assert res.status_code == 403

    def test_unauthenticated_cannot_book_appointment(self, api_client, counselor_user):
        res = api_client.post(f'/api/counselors/{counselor_user.counselor_profile.id}/book/', {})
        assert res.status_code == 401

    def test_unauthenticated_cannot_access_me(self, api_client):
        res = api_client.get('/api/auth/me/')
        assert res.status_code == 401

    def test_student_can_list_counselors(self, student_client):
        res = student_client.get('/api/counselors/')
        assert res.status_code == 200

    def test_student_cannot_upload_library_resource(self, student_client):
        res = student_client.post('/api/library/', {'title': 'test', 'resource_type': 'article'})
        assert res.status_code == 403
