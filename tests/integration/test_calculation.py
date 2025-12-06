import pytest
import uuid
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.models.calculation import AbstractCalculation, Modulo
from app.schemas.calculation import CalculationType

from app.main import app
from app.database import get_db

from app.models.calculation import (
    Calculation,
    Addition,
    Subtraction,
    Multiplication,
    Division,
    Modulo
)

# Helper function to create a dummy user_id for testing.
def dummy_user_id():
    return uuid.uuid4()

def test_addition_get_result():
    """
    Test that Addition.get_result returns the correct sum.
    """
    inputs = [10, 5, 3.5]
    addition = Addition(user_id=dummy_user_id(), inputs=inputs)
    result = addition.get_result()
    assert result == sum(inputs), f"Expected {sum(inputs)}, got {result}"

def test_subtraction_get_result():
    """
    Test that Subtraction.get_result returns the correct difference.
    """
    inputs = [20, 5, 3]
    subtraction = Subtraction(user_id=dummy_user_id(), inputs=inputs)
    # Expected: 20 - 5 - 3 = 12
    result = subtraction.get_result()
    assert result == 12, f"Expected 12, got {result}"

def test_multiplication_get_result():
    """
    Test that Multiplication.get_result returns the correct product.
    """
    inputs = [2, 3, 4]
    multiplication = Multiplication(user_id=dummy_user_id(), inputs=inputs)
    result = multiplication.get_result()
    assert result == 24, f"Expected 24, got {result}"

def test_division_get_result():
    """
    Test that Division.get_result returns the correct quotient.
    """
    inputs = [100, 2, 5]
    division = Division(user_id=dummy_user_id(), inputs=inputs)
    # Expected: 100 / 2 / 5 = 10
    result = division.get_result()
    assert result == 10, f"Expected 10, got {result}"

def test_division_by_zero():
    """
    Test that Division.get_result raises ValueError when dividing by zero.
    """
    inputs = [50, 0, 5]
    division = Division(user_id=dummy_user_id(), inputs=inputs)
    with pytest.raises(ValueError, match="Cannot divide by zero."):
        division.get_result()

def test_calculation_factory_addition():
    """
    Test the Calculation.create factory method for addition.
    """
    inputs = [1, 2, 3]
    calc = Calculation.create(
        calculation_type='addition',
        user_id=dummy_user_id(),
        inputs=inputs,
    )
    # Check that the returned instance is an Addition.
    assert isinstance(calc, Addition), "Factory did not return an Addition instance."
    assert calc.get_result() == sum(inputs), "Incorrect addition result."

def test_calculation_factory_subtraction():
    """
    Test the Calculation.create factory method for subtraction.
    """
    inputs = [10, 4]
    calc = Calculation.create(
        calculation_type='subtraction',
        user_id=dummy_user_id(),
        inputs=inputs,
    )
    # Expected: 10 - 4 = 6
    assert isinstance(calc, Subtraction), "Factory did not return a Subtraction instance."
    assert calc.get_result() == 6, "Incorrect subtraction result."

def test_calculation_factory_multiplication():
    """
    Test the Calculation.create factory method for multiplication.
    """
    inputs = [3, 4, 2]
    calc = Calculation.create(
        calculation_type='multiplication',
        user_id=dummy_user_id(),
        inputs=inputs,
    )
    # Expected: 3 * 4 * 2 = 24
    assert isinstance(calc, Multiplication), "Factory did not return a Multiplication instance."
    assert calc.get_result() == 24, "Incorrect multiplication result."

def test_calculation_factory_division():
    """
    Test the Calculation.create factory method for division.
    """
    inputs = [100, 2, 5]
    calc = Calculation.create(
        calculation_type='division',
        user_id=dummy_user_id(),
        inputs=inputs,
    )
    # Expected: 100 / 2 / 5 = 10
    assert isinstance(calc, Division), "Factory did not return a Division instance."
    assert calc.get_result() == 10, "Incorrect division result."

def test_calculation_factory_invalid_type():
    """
    Test that Calculation.create raises a ValueError for an unsupported calculation type.
    """
    with pytest.raises(ValueError, match="Unsupported calculation type"):
        Calculation.create(
            calculation_type='modulus',  # unsupported type
            user_id=dummy_user_id(),
            inputs=[10, 3],
        )

def test_invalid_inputs_for_addition():
    """
    Test that providing non-list inputs to Addition.get_result raises a ValueError.
    """
    addition = Addition(user_id=dummy_user_id(), inputs="not-a-list")
    with pytest.raises(ValueError, match="Inputs must be a list of numbers."):
        addition.get_result()

def test_invalid_inputs_for_subtraction():
    """
    Test that providing fewer than two numbers to Subtraction.get_result raises a ValueError.
    """
    subtraction = Subtraction(user_id=dummy_user_id(), inputs=[10])
    with pytest.raises(ValueError, match="Inputs must be a list with at least two numbers."):
        subtraction.get_result()

def test_invalid_inputs_for_division():
    """
    Test that providing fewer than two numbers to Division.get_result raises a ValueError.
    """
    division = Division(user_id=dummy_user_id(), inputs=[10])
    with pytest.raises(ValueError, match="Inputs must be a list with at least two numbers."):
        division.get_result()

######################### New tests ###########################


client = TestClient(app)

# Fake authenticated user object
class FakeUser:
    id = uuid.uuid4()

# Override authentication dependency
def override_current_user():
    return FakeUser()

app.dependency_overrides = {}
app.dependency_overrides[get_db] = lambda: MagicMock()
from app.auth.dependencies import get_current_active_user
app.dependency_overrides[get_current_active_user] = override_current_user

from datetime import datetime, timezone

def test_create_modulo_success():
    mock_db = MagicMock()

    app.dependency_overrides[get_db] = lambda: mock_db

    # patch factory to return a fake calc object
    fake_calc = MagicMock()
    fake_calc.id = uuid.uuid4()
    fake_calc.user_id = FakeUser().id
    fake_calc.type = "modulo"
    fake_calc.inputs = [10, 3]
    fake_calc.result = 1
    fake_calc.created_at = datetime.now(timezone.utc)
    fake_calc.updated_at = datetime.now(timezone.utc)

    with patch("app.models.calculation.Calculation.create", return_value=fake_calc):
        with patch.object(fake_calc, "get_result", return_value=1):
            response = client.post(
                "/calculations",
                json={
                    "type": "modulo",
                    "inputs": [10, 3]
                }
            )

    assert response.status_code == 201
    data = response.json()

    assert data["type"] == "modulo"
    assert data["inputs"] == [10, 3]
    assert data["result"] == 1


# def test_create_modulo_zero_divisor():
#     mock_db = MagicMock()
#     app.dependency_overrides[get_db] = lambda: mock_db

#     with patch("app.models.calculation.Calculation.create", side_effect=ValueError("Cannot modulo by zero")):
#         response = client.post(
#             "/calculations",
#             json={
#                 "type": "modulo",
#                 "inputs": [10, 0]
#             }
#         )

#     assert response.status_code == 400
#     assert "Cannot modulo by zero" in response.json()["detail"]

# def test_create_modulo_insufficient_inputs():
#     mock_db = MagicMock()
#     app.dependency_overrides[get_db] = lambda: mock_db

#     with patch("app.models.calculation.Calculation.create", side_effect=ValueError("At least two numbers are required")):
#         response = client.post(
#             "/calculations",
#             json={
#                 "type": "modulo",
#                 "inputs": [10]
#             }
#         )

#     assert response.status_code == 400
#     assert "two numbers" in response.json()["detail"]




# def test_factory_creates_modulo():
#     calc = AbstractCalculation.create("modulo", uuid.uuid4(), [10, 3])
#     assert isinstance(calc, Modulo)



# def test_modulo_enum_exists():
#     assert CalculationType.MODULO == "modulo"
