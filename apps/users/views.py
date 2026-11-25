from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import CustomUser
from .serializers import RegisterSerializer, UserProfileSerializer, CustomTokenObtainPairSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserProfileSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({'error': 'Refresh token required.'}, status=status.HTTP_400_BAD_REQUEST)
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class GoogleLoginView(APIView):
    """
    Sign in / sign up with Google.

    Follows Google's backend guidance: the client sends the ID token (`credential`) from
    Google Identity Services; we verify signature, `iss`, `exp` and `aud` (our client id)
    with google-auth, require a verified email, and key the account on the stable `sub`
    claim, never on email alone. We then issue our own JWTs; the Google token is discarded.
    """
    permission_classes = [AllowAny]
    throttle_scope = 'auth'

    def post(self, request):
        from django.conf import settings
        from google.oauth2 import id_token as google_id_token
        from google.auth.transport import requests as google_requests

        credential = request.data.get('credential')
        if not credential:
            return Response({'error': 'Missing Google credential.'}, status=status.HTTP_400_BAD_REQUEST)
        if not settings.GOOGLE_CLIENT_ID:
            return Response({'error': 'Google sign-in is not configured.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        try:
            info = google_id_token.verify_oauth2_token(
                credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
        except ValueError:
            return Response({'error': 'Invalid Google sign-in. Please try again.'}, status=status.HTTP_401_UNAUTHORIZED)

        if info.get('iss') not in ('accounts.google.com', 'https://accounts.google.com'):
            return Response({'error': 'Invalid token issuer.'}, status=status.HTTP_401_UNAUTHORIZED)
        if not info.get('email_verified'):
            return Response({'error': 'Your Google email is not verified.'}, status=status.HTTP_403_FORBIDDEN)

        sub, email = info['sub'], info['email'].lower()
        user = CustomUser.objects.filter(google_sub=sub).first()
        created = False
        if not user:
            existing = CustomUser.objects.filter(email__iexact=email).first()
            if existing:
                # Link only because Google asserts this exact email is verified.
                existing.google_sub = sub
                existing.save(update_fields=['google_sub'])
                user = existing
            else:
                if not request.data.get('consent_given'):
                    return Response(
                        {'error': 'consent_required', 'detail': 'Please accept the privacy policy to create an account.'},
                        status=status.HTTP_428_PRECONDITION_REQUIRED,
                    )
                base = email.split('@')[0][:20] or 'student'
                username, n = base, 0
                while CustomUser.objects.filter(username=username).exists():
                    n += 1
                    username = f'{base}{n}'
                user = CustomUser(
                    username=username, email=email, google_sub=sub,
                    first_name=info.get('given_name', '')[:150],
                    last_name=info.get('family_name', '')[:150],
                    role=CustomUser.Role.STUDENT,
                    consent_given=True, consent_given_at=timezone.now(),
                )
                user.set_unusable_password()
                user.save()
                created = True

        if not user.is_active:
            return Response({'error': 'This account is disabled.'}, status=status.HTTP_403_FORBIDDEN)

        refresh = CustomTokenObtainPairSerializer.get_token(user)
        return Response({
            'user': UserProfileSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'created': created,
        }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
