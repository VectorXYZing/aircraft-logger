import aircraft_logger


def test_parse_message_valid():
    parts = [""] * 22
    parts[4] = "AB1234"
    parts[10] = "CALL123"
    parts[11] = "35000"
    parts[12] = "450"
    parts[14] = "52.1"
    parts[15] = "-1.2"
    line = ",".join(parts)
    res = aircraft_logger.parse_message(line)
    assert res == ("AB1234", "CALL123", "35000", "450", "52.1", "-1.2")


def test_parse_message_invalid():
    assert aircraft_logger.parse_message("too,short") is None
