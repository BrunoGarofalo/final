# tests/integration/test_user_auth.py

import pytest
from uuid import UUID
import uuid
import pydantic_core
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import datetime, timezone, timedelta
from jose import jwt
from datetime import datetime, timedelta

from app.auth.jwt import decode_token, TokenType
from app.core.config import settings

from app.main import app, get_db
from fastapi.testclient import TestClient

client = TestClient(app)

def test_password_hashing(db_session, fake_user_data):
    """Test password hashing and verification functionality"""
    original_password = "TestPass123"  # Use known password for test
    hashed = User.hash_password(original_password)
    
    user = User(
        first_name=fake_user_data['first_name'],
        last_name=fake_user_data['last_name'],
        email=fake_user_data['email'],
        username=fake_user_data['username'],
        password=hashed
    )
    
    assert user.verify_password(original_password) is True
    assert user.verify_password("WrongPass123") is False
    assert hashed != original_password

def test_user_registration(db_session, fake_user_data):
    """Test user registration process"""
    fake_user_data['password'] = "TestPass123"
    
    user = User.register(db_session, fake_user_data)
    db_session.commit()
    
    assert user.first_name == fake_user_data['first_name']
    assert user.last_name == fake_user_data['last_name']
    assert user.email == fake_user_data['email']
    assert user.username == fake_user_data['username']
    assert user.is_active is True
    assert user.is_verified is False
    assert user.verify_password("TestPass123") is True

def test_duplicate_user_registration(db_session):
    """Test registration with duplicate email/username"""
    # First user data
    user1_data = {
        "first_name": "Test",
        "last_name": "User1",
        "email": "unique.test@example.com",
        "username": "uniqueuser1",
        "password": "TestPass123"
    }
    
    # Second user data with same email
    user2_data = {
        "first_name": "Test",
        "last_name": "User2",
        "email": "unique.test@example.com",  # Same email
        "username": "uniqueuser2",
        "password": "TestPass123"
    }
    
    # Register first user
    first_user = User.register(db_session, user1_data)
    db_session.commit()
    db_session.refresh(first_user)
    
    # Try to register second user with same email
    with pytest.raises(ValueError, match="Username or email already exists"):
        User.register(db_session, user2_data)

def test_user_authentication(db_session, fake_user_data):
    """Test user authentication and token generation"""
    # Use fake_user_data from fixture
    fake_user_data['password'] = "TestPass123"
    user = User.register(db_session, fake_user_data)
    db_session.commit()
    
    # Test successful authentication
    auth_result = User.authenticate(
        db_session,
        fake_user_data['username'],
        "TestPass123"
    )
    
    assert auth_result is not None
    assert "access_token" in auth_result
    assert "token_type" in auth_result
    assert auth_result["token_type"] == "bearer"
    assert "user" in auth_result

def test_user_last_login_update(db_session, fake_user_data):
    """Test that last_login is updated on authentication"""
    fake_user_data['password'] = "TestPass123"
    user = User.register(db_session, fake_user_data)
    db_session.commit()
    
    # Authenticate and check last_login
    assert user.last_login is None
    auth_result = User.authenticate(db_session, fake_user_data['username'], "TestPass123")
    db_session.refresh(user)
    assert user.last_login is not None

def test_unique_email_username(db_session):
    """Test uniqueness constraints for email and username"""
    # Create first user with specific test data
    user1_data = {
        "first_name": "Test",
        "last_name": "User1",
        "email": "unique_test@example.com",
        "username": "uniqueuser",
        "password": "TestPass123"
    }
    
    # Register and commit first user
    User.register(db_session, user1_data)
    db_session.commit()
    
    # Try to create user with same email
    user2_data = {
        "first_name": "Test",
        "last_name": "User2",
        "email": "unique_test@example.com",  # Same email
        "username": "differentuser",
        "password": "TestPass123"
    }
    
    with pytest.raises(ValueError, match="Username or email already exists"):
        User.register(db_session, user2_data)

def test_short_password_registration(db_session):
    """Test that registration fails with a short password"""
    # Prepare test data with a 5-character password
    test_data = {
        "first_name": "Password",
        "last_name": "Test",
        "email": "short.pass@example.com",
        "username": "shortpass",
        "password": "Shor1"  # 5 characters, should fail
    }
    
    # Attempt registration with short password
    with pytest.raises(ValueError, match="Password must be at least 6 characters long"):
        User.register(db_session, test_data)

def test_invalid_token():
    """Test that invalid tokens are rejected"""
    invalid_token = "invalid.token.string"
    result = User.verify_token(invalid_token)
    assert result is None

def test_token_creation_and_verification(db_session, fake_user_data):
    """Test token creation and verification"""
    fake_user_data['password'] = "TestPass123"
    user = User.register(db_session, fake_user_data)
    db_session.commit()
    
    # Create token
    token = User.create_access_token({"sub": str(user.id)})
    
    # Verify token
    decoded_user_id = User.verify_token(token)
    assert decoded_user_id == user.id

def test_authenticate_with_email(db_session, fake_user_data):
    """Test authentication using email instead of username"""
    fake_user_data['password'] = "TestPass123"
    user = User.register(db_session, fake_user_data)
    db_session.commit()
    
    # Test authentication with email
    auth_result = User.authenticate(
        db_session,
        fake_user_data['email'],  # Using email instead of username
        "TestPass123"
    )
    
    assert auth_result is not None
    assert "access_token" in auth_result

def test_user_model_representation(test_user):
    """Test the string representation of User model"""
    expected = f"<User(name={test_user.first_name} {test_user.last_name}, email={test_user.email})>"
    assert str(test_user) == expected

def test_missing_password_registration(db_session):
    """Test that registration fails when no password is provided."""
    test_data = {
        "first_name": "NoPassword",
        "last_name": "Test",
        "email": "no.password@example.com",
        "username": "nopassworduser",
        # Password is missing
    }
    
    # Adjust the expected error message
    with pytest.raises(ValueError, match="Password must be at least 6 characters long"):
        User.register(db_session, test_data)


@pytest.mark.asyncio
async def test_decode_token_success():
    jti = "abc123"

    payload = {
        "sub": "user123",
        "type": TokenType.ACCESS.value,
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "jti": jti,
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)

    with patch("app.auth.jwt.is_blacklisted", new=AsyncMock(return_value=False)):
        decoded = await decode_token(token, TokenType.ACCESS)

    assert decoded["sub"] == "user123"
    assert decoded["type"] == TokenType.ACCESS.value
    assert decoded["jti"] == jti




@pytest.mark.asyncio
async def test_decode_token_invalid_type():
    payload = {
        "sub": "user123",
        "type": TokenType.REFRESH.value,  # Wrong type
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "jti": "jti123",
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)

    with patch("app.auth.jwt.is_blacklisted", new=AsyncMock(return_value=False)):
        with pytest.raises(Exception) as exc:
            await decode_token(token, TokenType.ACCESS)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token type"



@pytest.mark.asyncio
async def test_decode_token_blacklisted():
    payload = {
        "sub": "user123",
        "type": TokenType.ACCESS.value,
        "exp": datetime.utcnow() + timedelta(minutes=5),
        "jti": "blocked123",
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)

    # FIXED PATCH PATH ↓↓↓
    with patch("app.auth.jwt.is_blacklisted", new=AsyncMock(return_value=True)):
        with pytest.raises(Exception) as exc:
            await decode_token(token, TokenType.ACCESS)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token has been revoked"


@pytest.mark.asyncio
async def test_decode_token_expired():
    payload = {
        "sub": "user123",
        "type": TokenType.ACCESS.value,
        "exp": datetime.utcnow() - timedelta(minutes=1),  # expired
        "jti": "expired123",
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)

    with patch("app.auth.jwt.is_blacklisted", new=AsyncMock(return_value=False)):
        with pytest.raises(Exception) as exc:
            await decode_token(token, TokenType.ACCESS)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token has expired"


@pytest.mark.asyncio
async def test_decode_token_invalid_signature():
    invalid_token = "not.a.valid.jwt"

    with pytest.raises(Exception) as exc:
        await decode_token(invalid_token, TokenType.ACCESS)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Could not validate credentials"

def setup_overrides(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db

def test_login_form_success():
    mock_db = MagicMock()
    setup_overrides(mock_db)

    auth_result = {
        "access_token": "access123",
        "refresh_token": "refresh123",  # not used here
        "user": MagicMock(),            # not needed but harmless
    }

    with patch.object(User, "authenticate", return_value=auth_result) as mock_auth:
        response = client.post(
            "/auth/token",
            data={
                "username": "john",
                "password": "secret123"
            }
        )

    assert response.status_code == 200

    data = response.json()
    assert data["access_token"] == "access123"
    assert data["token_type"] == "bearer"

    # ensure authenticate was called properly
    mock_auth.assert_called_once_with(mock_db, "john", "secret123")

def test_login_form_invalid_credentials():
    mock_db = MagicMock()
    setup_overrides(mock_db)

    with patch.object(User, "authenticate", return_value=None):
        response = client.post(
            "/auth/token",
            data={
                "username": "wrong",
                "password": "invalid"
            }
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"


def test_login_form_missing_fields():
    mock_db = MagicMock()
    setup_overrides(mock_db)

    response = client.post("/auth/token", data={"username": "john"})

    assert response.status_code == 422
