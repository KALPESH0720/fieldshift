
import pytest

from pipelines.p1_grid_layers.pipeline import (
    GridPipelineError,
    prepare_grid_layers,
    run_p1_grid_pipeline,
    validate_grid_input,
)


@pytest.fixture
def valid_grid_input():
    return {
        "latitude": 15.4909,
        "longitude": 73.8278,
        "weather": {"rainfall_mm": 2200, "temperature_mean_c": 27.5},
        "soil": {"ph": 6.2, "texture": "loam"},
        "satellite": {"ndvi": 0.62},
        "crop_history": [
            {"season": "Kharif-2024", "crop": "rice"},
            {"season": "Rabi-2024", "crop": "groundnut"},
        ],
        "metadata": {"dataset": "pilot"},
    }


def test_validate_grid_input_accepts_valid_coordinates(
    valid_grid_input,
):
    validate_grid_input(valid_grid_input)


def test_prepare_grid_layers_preserves_all_layers(
    valid_grid_input,
):
    bundle = prepare_grid_layers(valid_grid_input)

    assert bundle.latitude == pytest.approx(15.4909)
    assert bundle.longitude == pytest.approx(73.8278)
    assert bundle.grid_id == "grid_15.4909_73.8278"

    assert bundle.weather == valid_grid_input["weather"]
    assert bundle.soil == valid_grid_input["soil"]
    assert bundle.satellite == valid_grid_input["satellite"]
    assert bundle.crop_history == valid_grid_input["crop_history"]


def test_prepare_grid_layers_converts_coordinates():
    data = {
        "latitude": "15.49",
        "longitude": "73.82",
    }

    bundle = prepare_grid_layers(data)

    assert bundle.latitude == 15.49
    assert bundle.longitude == 73.82


def test_prepare_grid_layers_uses_custom_grid_id():
    data = {
        "latitude": 15.49,
        "longitude": 73.82,
        "grid_id": "GOA-PILOT-001",
    }

    bundle = prepare_grid_layers(data)

    assert bundle.grid_id == "GOA-PILOT-001"


def test_prepare_grid_layers_creates_availability_metadata(
    valid_grid_input,
):
    bundle = prepare_grid_layers(valid_grid_input)

    assert bundle.metadata["layer_availability"] == {
        "weather": True,
        "soil": True,
        "satellite": True,
        "crop_history": True,
    }

    assert bundle.metadata["latitude"] == 15.4909
    assert bundle.metadata["longitude"] == 73.8278
    assert bundle.metadata["dataset"] == "pilot"


def test_prepare_grid_layers_handles_missing_optional_layers():
    data = {
        "latitude": 15.49,
        "longitude": 73.82,
    }

    bundle = prepare_grid_layers(data)

    assert bundle.weather == {}
    assert bundle.soil == {}
    assert bundle.satellite == {}
    assert bundle.crop_history == []

    assert bundle.metadata["layer_availability"] == {
        "weather": False,
        "soil": False,
        "satellite": False,
        "crop_history": False,
    }


def test_bundle_to_dict_contains_expected_keys(
    valid_grid_input,
):
    bundle = prepare_grid_layers(valid_grid_input)

    result = bundle.to_dict()

    assert set(result.keys()) == {
        "grid_id",
        "latitude",
        "longitude",
        "weather",
        "soil",
        "satellite",
        "crop_history",
        "metadata",
    }


def test_run_p1_grid_pipeline_returns_success_structure(
    valid_grid_input,
):
    result = run_p1_grid_pipeline(valid_grid_input)

    assert result["stage"] == "p1_grid_layers"
    assert result["status"] == "success"
    assert result["grid"]["grid_id"] == "grid_15.4909_73.8278"
    assert result["grid"]["weather"] == valid_grid_input["weather"]
    assert result["grid"]["soil"] == valid_grid_input["soil"]
    assert result["grid"]["satellite"] == valid_grid_input["satellite"]


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"latitude": 15.49},
        {"longitude": 73.82},
    ],
)
def test_validate_grid_input_rejects_missing_coordinates(data):
    with pytest.raises(
        GridPipelineError,
        match="Latitude and longitude are required",
    ):
        validate_grid_input(data)


@pytest.mark.parametrize(
    ("latitude", "longitude", "message"),
    [
        ("invalid", 73.82, "latitude must be numeric"),
        (15.49, "invalid", "longitude must be numeric"),
        (float("nan"), 73.82, "latitude must be finite"),
        (15.49, float("inf"), "longitude must be finite"),
        (91, 73.82, "Latitude must be between -90 and 90"),
        (-91, 73.82, "Latitude must be between -90 and 90"),
        (15.49, 181, "Longitude must be between -180 and 180"),
        (15.49, -181, "Longitude must be between -180 and 180"),
    ],
)
def test_validate_grid_input_rejects_invalid_coordinates(
    latitude,
    longitude,
    message,
):
    with pytest.raises(GridPipelineError, match=message):
        validate_grid_input(
            {
                "latitude": latitude,
                "longitude": longitude,
            }
        )


@pytest.mark.parametrize(
    "crop_history",
    [
        ["rice"],
        [None],
        [123],
    ],
)
def test_prepare_grid_layers_rejects_invalid_crop_history(
    crop_history,
):
    with pytest.raises(
        GridPipelineError,
        match="Each crop history record must be a mapping",
    ):
        prepare_grid_layers(
            {
                "latitude": 15.49,
                "longitude": 73.82,
                "crop_history": crop_history,
            }
        )
