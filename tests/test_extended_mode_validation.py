import pytest
from pydantic import ValidationError
from rdetoolkit.models.config import SystemSettings, Config


class TestExtendedModeValidation:
    """Test cases for extended_mode validation."""

    def test_valid_extended_mode_none(self):
        """Test that None is a valid extended_mode (invoice mode)."""
        settings = SystemSettings(extended_mode=None)
        assert settings.extended_mode is None

    def test_valid_extended_mode_rdeformat(self):
        """Test that 'rdeformat' is a valid extended_mode."""
        settings = SystemSettings(extended_mode="rdeformat")
        assert settings.extended_mode == "rdeformat"

    def test_valid_extended_mode_multidatatile(self):
        """Test that 'MultiDataTile' is a valid extended_mode."""
        settings = SystemSettings(extended_mode="MultiDataTile")
        assert settings.extended_mode == "MultiDataTile"

    def test_invalid_extended_mode_lowercase_multidatatile(self):
        """Test that 'multidatatile' raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettings(extended_mode="multidatatile")

        error = exc_info.value.errors()[0]
        assert error['type'] == 'value_error'
        assert 'Invalid extended_mode "multidatatile"' in error['msg']

    def test_invalid_extended_mode_underscore_multidata_tile(self):
        """Test that 'multidata_tile' raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettings(extended_mode="multidata_tile")

        error = exc_info.value.errors()[0]
        assert error['type'] == 'value_error'
        assert 'Invalid extended_mode "multidata_tile"' in str(error['ctx'])

    def test_invalid_extended_mode_multi_data_tile(self):
        """Test that 'multi_data_tile' raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettings(extended_mode="multi_data_tile")

        error = exc_info.value.errors()[0]
        assert error['type'] == 'value_error'
        assert 'Invalid extended_mode "multi_data_tile"' in str(error['ctx'])

    def test_invalid_extended_mode_mixed_case(self):
        """Test that 'Multi_Data_Tile' raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettings(extended_mode="Multi_Data_Tile")

        error = exc_info.value.errors()[0]
        assert error['type'] == 'value_error'
        assert 'Invalid extended_mode "Multi_Data_Tile"' in str(error['ctx'])

    def test_invalid_extended_mode_uppercase_multidatatile(self):
        """Test that 'MULTIDATATILE' raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettings(extended_mode="MULTIDATATILE")

        error = exc_info.value.errors()[0]
        assert error['type'] == 'value_error'
        assert 'Invalid extended_mode "MULTIDATATILE"' in str(error['ctx'])

    def test_invalid_extended_mode_random_string(self):
        """Test that any other string raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettings(extended_mode="invalid_mode")

        error = exc_info.value.errors()[0]
        assert error['type'] == 'value_error'
        assert 'Invalid extended_mode "invalid_mode"' in str(error['ctx'])

    def test_config_with_valid_extended_mode(self):
        """Test that Config works with valid extended_mode."""
        config = Config(system=SystemSettings(extended_mode="MultiDataTile"))
        assert config.system.extended_mode == "MultiDataTile"

    def test_config_with_invalid_extended_mode(self):
        """Test that Config raises ValidationError with invalid extended_mode."""
        with pytest.raises(ValidationError) as exc_info:
            Config(system=SystemSettings(extended_mode="multidatatile"))

        error = exc_info.value.errors()[0]
        assert error['type'] == 'value_error'
        assert 'Invalid extended_mode "multidatatile"' in str(error['ctx'])

    def test_validation_error_message_format(self):
        """Test that validation error message includes valid options."""
        with pytest.raises(ValidationError) as exc_info:
            SystemSettings(extended_mode="invalid")

        error = exc_info.value.errors()[0]
        error_msg = str(error['ctx'])
        assert 'rdeformat' in error_msg
        assert 'MultiDataTile' in error_msg
        assert 'Valid options are:' in error_msg
