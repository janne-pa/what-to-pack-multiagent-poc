import json

import pytest

from what_to_pack.json_utils import safe_load_validated


@pytest.mark.parametrize("raw", ["null", "[1]", "true", "42", '"text"', "not json"])
def test_non_objects_are_rejected(raw):
    data, warnings = safe_load_validated(raw, ["destination"])
    assert data == {}
    assert warnings


@pytest.mark.parametrize(
    ("data", "keys"),
    [
        ({"destination": "Helsinki"}, ["destination", "duration", "travel_type"]),
        ({"destination": ""}, ["destination"]),
        ({"destination": None}, ["destination"]),
        ({"duration": -3}, ["duration"]),
        ({"duration": 0}, ["duration"]),
        ({"duration": True}, ["duration"]),
        ({"duration": "5"}, ["duration"]),
        ({"travel_type": 42}, ["travel_type"]),
        ({"latitude": True, "longitude": 24}, ["latitude", "longitude"]),
        ({"latitude": 91, "longitude": 24}, ["latitude", "longitude"]),
        ({"latitude": 60, "longitude": -181}, ["latitude", "longitude"]),
        ({"latitude": float("nan"), "longitude": 24}, ["latitude", "longitude"]),
        ({"latitude": 60, "longitude": float("inf")}, ["latitude", "longitude"]),
        ({"packing_notes": "coat"}, ["packing_notes"]),
        ({"packing_notes": [None]}, ["packing_notes"]),
        ({"packing_notes": []}, ["packing_notes"]),
        ({"weather_summary": {}}, ["weather_summary"]),
    ],
)
def test_invalid_fields_are_rejected(data, keys):
    result, warnings = safe_load_validated(json.dumps(data), keys)
    assert result == {}
    assert warnings


def test_fenced_valid_response():
    data, warnings = safe_load_validated(
        '```json\n{"destination":"Helsinki","duration":5,"travel_type":"business"}\n```',
        ["destination", "duration", "travel_type"],
    )
    assert data == {"destination": "Helsinki", "duration": 5, "travel_type": "business"}
    assert warnings == []


def test_coordinate_boundaries():
    data, warnings = safe_load_validated(
        '{"latitude":-90,"longitude":180}', ["latitude", "longitude"]
    )
    assert data == {"latitude": -90, "longitude": 180}
    assert warnings == []
