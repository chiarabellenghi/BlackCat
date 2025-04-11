import pytest
from blackcat.core import BlackCat


@pytest.fixture
def blackcat():
    # Create a BlackCat instance for testing
    return BlackCat(
        base_dir="../",
        config_file="../config.cfg",
    )
