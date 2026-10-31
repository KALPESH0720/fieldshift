import pytest
from pydantic import ValidationError

from app.schemas.auth import OTPRequest, OTPVerify
from app.schemas.plot import PlotCreate, PlotUpdate
from app.schemas.sync import SyncAction, SyncOperation, SyncPayload


@pytest.mark.parametrize("phone", ["9876543210", "+919876543210", "+14155552671"])
def test_auth_accepts_supported_phone_formats(phone):
    expected = "+919876543210" if phone == "9876543210" else phone
    assert OTPRequest(phone=phone).phone == expected


@pytest.mark.parametrize("phone", ["12345", "0123456789", "+01234567890", "phone"])
def test_auth_rejects_invalid_phone(phone):
    with pytest.raises(ValidationError):
        OTPRequest(phone=phone)


def test_otp_requires_numeric_code():
    assert OTPVerify(phone="9876543210", otp="001234").otp == "001234"
    with pytest.raises(ValidationError):
        OTPVerify(phone="9876543210", otp="12ab")


def test_plot_requires_positive_area_and_accepts_geojson_point():
    plot = PlotCreate(
        name="North field",
        area_acres=1.25,
        location={"type": "Point", "coordinates": [77.59, 12.97]},
    )
    assert plot.area_acres == 1.25
    with pytest.raises(ValidationError):
        PlotCreate(name="North field", area_acres=0)


def test_polygon_requires_closed_ring_and_update_requires_a_field():
    with pytest.raises(ValidationError):
        PlotCreate(
            name="Field",
            area_acres=1,
            location={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1]]]},
        )
    with pytest.raises(ValidationError):
        PlotUpdate()


def test_sync_operation_shape_and_extra_field_rejection():
    operation = SyncOperation(
        operation_id="op-1",
        entity="plot",
        action=SyncAction.UPDATE,
        updated_at="2026-10-30T10:00:00Z",
        data={"name": "West field"},
    )
    assert operation.action == SyncAction.UPDATE
    with pytest.raises(ValidationError):
        SyncPayload(client_id="client-1", operations=[], unexpected=True)
