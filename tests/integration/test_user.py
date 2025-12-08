# ======================================================================================
# tests/integration/test_user.py
# ======================================================================================
# Purpose: Demonstrate user model interactions with the database using pytest fixtures.
#          Relies on 'conftest.py' for database session management and test isolation.
# ======================================================================================

import pytest
import logging
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from app.main import app
from unittest.mock import MagicMock, patch
import uuid
from app.database import get_db
from datetime import datetime, timedelta, timezone


from app.models.user import User
from tests.conftest import create_fake_user, managed_db_session

# Use the logger configured in conftest.py
logger = logging.getLogger(__name__)
from fastapi.testclient import TestClient

client = TestClient(app)



# ======================================================================================
# Basic Connection & Session Tests
# ======================================================================================

def test_database_connection(db_session):
    """
    Verify that the database connection is working.
    
    Uses the db_session fixture from conftest.py, which truncates tables after each test.
    """
    result = db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1
    logger.info("Database connection test passed")


def test_managed_session():
    """
    Test the managed_db_session context manager for one-off queries and rollbacks.
    Demonstrates how a manual session context can work alongside the fixture-based approach.
    """
    with managed_db_session() as session:
        # Simple query
        session.execute(text("SELECT 1"))
        
        # Generate an error to trigger rollback
        try:
            session.execute(text("SELECT * FROM nonexistent_table"))
        except Exception as e:
            assert "nonexistent_table" in str(e)

# ======================================================================================
# Session Handling & Partial Commits
# ======================================================================================
def test_session_handling(db_session):
    """
    Demonstrate partial commits:
      - user1 is committed successfully.
      - user2 fails (due to duplicate email), triggering a rollback.
      - user3 is committed successfully.
      - The final user count should be the initial count plus two (user1 and user3).
    """
    # Use the current user count as our baseline.
    initial_count = db_session.query(User).count()
    logger.info(f"Initial user count before test_session_handling: {initial_count}")

    # Create and commit user1.
    user1 = User(
        first_name="User",
        last_name="One",
        email="user1@example.com",
        username="user1",
        password="hashed_password"
    )
    db_session.add(user1)
    db_session.commit()

    # Attempt to create user2 with a duplicate email (should fail).
    user2 = User(
        first_name="User",
        last_name="Two",
        email="user1@example.com",  # Duplicate email
        username="user2",
        password="hashed_password"
    )
    db_session.add(user2)
    try:
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        logger.info(f"Expected failure on duplicate user2: {e}")

    # Create and commit user3 with unique email/username.
    user3 = User(
        first_name="User",
        last_name="Three",
        email="user3@example.com",
        username="user3",
        password="hashed_password"
    )
    db_session.add(user3)
    db_session.commit()

    # Verify that only two additional users have been added.
    final_count = db_session.query(User).count()
    expected_final = initial_count + 2
    assert final_count == expected_final, (
        f"Expected {expected_final} users after test, found {final_count}"
    )

# ======================================================================================
# User Creation Tests
# ======================================================================================

def test_create_user_with_faker(db_session):
    """
    Create a single user using Faker-generated data and verify it was saved.
    """
    user_data = create_fake_user()
    logger.info(f"Creating user with data: {user_data}")
    
    user = User(**user_data)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)  # Refresh populates fields like user.id
    
    assert user.id is not None
    assert user.email == user_data["email"]
    logger.info(f"Successfully created user with ID: {user.id}")


def test_create_multiple_users(db_session):
    """
    Create multiple users in a loop and verify they are all saved.
    """
    users = []
    for _ in range(3):
        user_data = create_fake_user()
        user = User(**user_data)
        users.append(user)
        db_session.add(user)
    
    db_session.commit()
    assert len(users) == 3
    logger.info(f"Successfully created {len(users)} users")

# ======================================================================================
# Query Tests
# ======================================================================================

def test_query_methods(db_session, seed_users):
    """
    Illustrate various query methods using seeded users.
    
    - Counting all users
    - Filtering by email
    - Ordering by email
    """
    user_count = db_session.query(User).count()
    assert user_count >= len(seed_users), "The user table should have at least the seeded users"
    
    first_user = seed_users[0]
    found = db_session.query(User).filter_by(email=first_user.email).first()
    assert found is not None, "Should find the seeded user by email"
    
    users_by_email = db_session.query(User).order_by(User.email).all()
    assert len(users_by_email) >= len(seed_users), "Query should return at least the seeded users"

# ======================================================================================
# Transaction / Rollback Tests
# ======================================================================================

def test_transaction_rollback(db_session):
    """
    Demonstrate how a partial transaction fails and triggers rollback.
    - We add a user and force an error
    - We catch the error and rollback
    - Verify the user was not committed
    """
    initial_count = db_session.query(User).count()
    
    try:
        user_data = create_fake_user()
        user = User(**user_data)
        db_session.add(user)
        # Force an error to trigger rollback
        db_session.execute(text("SELECT * FROM nonexistent_table"))
        db_session.commit()
    except Exception:
        db_session.rollback()
    
    final_count = db_session.query(User).count()
    assert final_count == initial_count, "The new user should not have been committed"

# ======================================================================================
# Update Tests
# ======================================================================================

def test_update_with_refresh(db_session, test_user):
    """
    Update a user's email and refresh the session to see updated fields.
    """
    original_email = test_user.email
    original_update_time = test_user.updated_at
    
    new_email = f"new_{original_email}"
    test_user.email = new_email
    db_session.commit()
    db_session.refresh(test_user)  # Refresh to populate any updated_at or other fields
    
    assert test_user.email == new_email, "Email should have been updated"
    assert test_user.updated_at > original_update_time, "Updated time should be newer"
    logger.info(f"Successfully updated user {test_user.id}")

# ======================================================================================
# Bulk Operation Tests
# ======================================================================================

@pytest.mark.slow
def test_bulk_operations(db_session):
    """
    Test bulk inserting multiple users at once (marked slow).
    Use --run-slow to enable this test.
    """
    users_data = [create_fake_user() for _ in range(10)]
    users = [User(**data) for data in users_data]
    db_session.bulk_save_objects(users)
    db_session.commit()
    
    count = db_session.query(User).count()
    assert count >= 10, "At least 10 users should now be in the database"
    logger.info(f"Successfully performed bulk operation with {len(users)} users")

# ======================================================================================
# Uniqueness Constraint Tests
# ======================================================================================

def test_unique_email_constraint(db_session):
    """
    Create two users with the same email and expect an IntegrityError.
    """
    first_user_data = create_fake_user()
    first_user = User(**first_user_data)
    db_session.add(first_user)
    db_session.commit()
    
    second_user_data = create_fake_user()
    second_user_data["email"] = first_user_data["email"]  # Force a duplicate email
    second_user = User(**second_user_data)
    db_session.add(second_user)
    
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_unique_username_constraint(db_session):
    """
    Create two users with the same username and expect an IntegrityError.
    """
    first_user_data = create_fake_user()
    first_user = User(**first_user_data)
    db_session.add(first_user)
    db_session.commit()
    
    second_user_data = create_fake_user()
    second_user_data["username"] = first_user_data["username"]  # Force a duplicate username
    second_user = User(**second_user_data)
    db_session.add(second_user)
    
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

# ======================================================================================
# Persistence after Constraint Violation
# ======================================================================================

def test_user_persistence_after_constraint(db_session):
    """
    - Create and commit a valid user
    - Attempt to create a duplicate user (same email) -> fails
    - Confirm the original user still exists
    """
    initial_user_data = {
        "first_name": "First",
        "last_name": "User",
        "email": "first@example.com",
        "username": "firstuser",
        "password": "password123"
    }
    initial_user = User(**initial_user_data)
    db_session.add(initial_user)
    db_session.commit()
    saved_id = initial_user.id
    
    try:
        duplicate_user = User(
            first_name="Second",
            last_name="User",
            email="first@example.com",  # Duplicate
            username="seconduser",
            password="password456"
        )
        db_session.add(duplicate_user)
        db_session.commit()
        assert False, "Should have raised IntegrityError"
    except IntegrityError:
        db_session.rollback()
    
    found_user = db_session.query(User).filter_by(id=saved_id).first()
    assert found_user is not None, "Original user should exist"
    assert found_user.id == saved_id, "Should find original user by ID"
    assert found_user.email == "first@example.com", "Email should be unchanged"
    assert found_user.username == "firstuser", "Username should be unchanged"

# ======================================================================================
# Error Handling Test
# ======================================================================================

def test_error_handling():
    """
    Verify that a manual managed_db_session can capture and log invalid SQL errors.
    """
    with pytest.raises(Exception) as exc_info:
        with managed_db_session() as session:
            session.execute(text("INVALID SQL"))
    assert "INVALID SQL" in str(exc_info.value)



def test_register_success(monkeypatch):
    # Fake user returned by the register method
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.username = "john"
    mock_user.email = "john@example.com"
    mock_user.first_name = "John"
    mock_user.last_name = "Doe"
    mock_user.is_active = True
    mock_user.is_verified = False

    # Patch User.register
    monkeypatch.setattr(
        "app.models.user.User.register",
        lambda db, data: mock_user
    )

    # Mock DB session object
    mock_db = MagicMock()
    mock_db.commit = MagicMock()
    mock_db.refresh = MagicMock()

    # Correct way to override dependency
    app.dependency_overrides[get_db] = lambda: mock_db

    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "username": "john",
        "password": "SecurePass123!",
        "confirm_password": "SecurePass123!",
    }

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 201
    data = response.json()

    assert data["username"] == "john"
    assert data["email"] == "john@example.com"

    # cleanup
    app.dependency_overrides.clear()


def test_register_value_error(monkeypatch):
    # Force an error when User.register is called
    def mock_register(db, data):
        raise ValueError("Email already exists")

    # Patch User.register to throw error
    monkeypatch.setattr("app.models.user.User.register", mock_register)

    # Mock database session
    mock_db = MagicMock()

    # CORRECT dependency override
    app.dependency_overrides[get_db] = lambda: mock_db

    payload = {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john@example.com",
        "username": "john",
        "password": "SecurePass123!",
        "confirm_password": "SecurePass123!",
    }

    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    assert response.json()["detail"] == "Email already exists"

    # cleanup
    app.dependency_overrides.clear()

def setup_overrides(mock_db):
    app.dependency_overrides[get_db] = lambda: mock_db

def test_login_invalid_credentials():
    mock_db = MagicMock()
    setup_overrides(mock_db)

    with patch.object(User, "authenticate", return_value=None):
        response = client.post(
            "/auth/login",
            json={"username": "wrong", "password": "wrongpass"}
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password"

    mock_db.commit.assert_not_called()

def test_login_success():
    mock_db = MagicMock()
    setup_overrides(mock_db)

    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()  # FIXED
    mock_user.username = "john"
    mock_user.email = "john@example.com"
    mock_user.first_name = "John"
    mock_user.last_name = "Doe"
    mock_user.is_active = True
    mock_user.is_verified = True

    auth_result = {
        "user": mock_user,
        "access_token": "access123",
        "refresh_token": "refresh123",
        "expires_at": datetime.now(),  # naive datetime is fine
    }

    with patch.object(User, "authenticate", return_value=auth_result):
        response = client.post(
            "/auth/login",
            json={"username": "john", "password": "secret123"}
        )

    assert response.status_code == 200
    data = response.json()

    assert data["access_token"] == "access123"
    assert data["refresh_token"] == "refresh123"
    assert data["token_type"] == "bearer"
    assert data["user_id"] == str(mock_user.id)  # UUID becomes string

def test_register_calls_db_add(monkeypatch):
    mock_db = MagicMock()

    # Patch hash_password to avoid hashing during the test
    monkeypatch.setattr(User, "hash_password", lambda pwd: "hashed123")

    user_data = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice@example.com",
        "username": "alice",
        "password": "StrongPass123"
    }

    # Simulate no existing user
    mock_db.query.return_value.filter.return_value.first.return_value = None

    user = User.register(mock_db, user_data)

    # db.add() should be called with the created user instance
    mock_db.add.assert_called_once_with(user)

    # Ensure password hashing happened
    assert user.password == "hashed123"

def test_register_calls_hash_password(monkeypatch):
    mock_db = MagicMock()

    # Spy on hash_password
    mock_hash = MagicMock(return_value="hashed321")
    monkeypatch.setattr(User, "hash_password", mock_hash)

    user_data = {
        "first_name": "Bob",
        "last_name": "Johnson",
        "email": "bob@example.com",
        "username": "bobby",
        "password": "MySecretPass"
    }

    # Simulate no duplicate user found
    mock_db.query.return_value.filter.return_value.first.return_value = None

    user = User.register(mock_db, user_data)

    # Verify the password hashing method was called correctly
    mock_hash.assert_called_once_with("MySecretPass")

    # And the resulting user has the hashed password applied
    assert user.password == "hashed321"
