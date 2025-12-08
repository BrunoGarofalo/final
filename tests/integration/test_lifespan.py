import pytest
from unittest.mock import patch, MagicMock, call
from app.main import lifespan
from sqlalchemy.orm import DeclarativeMeta


@pytest.mark.asyncio
async def test_lifespan_creates_tables(capsys):
    """
    Test that the FastAPI lifespan function calls Base.metadata.create_all
    and prints the correct startup messages.
    """

    # Patch Base.metadata.create_all
    with patch("app.main.Base.metadata.create_all") as mock_create_all, \
         patch("app.main.engine", MagicMock()):

        # Enter the lifespan context manually
        async with lifespan(None):
            pass  # lifespan yields here

        # Assert create_all was called once with "engine"
        mock_create_all.assert_called_once()

    # Capture printed output
    captured = capsys.readouterr()

    assert "Creating tables..." in captured.out
    assert "Tables created successfully!" in captured.out
