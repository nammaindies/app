from app.ids import uuid7


def test_uuid7_is_version_7_and_time_ordered():
    a = uuid7()
    b = uuid7()
    assert a.version == 7
    assert a < b  # v7 is monotonic by time
