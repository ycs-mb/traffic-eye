"""Tests for Indian plate validators."""

from src.ocr.validators import (
    clean_plate_text,
    correct_ocr_errors,
    extract_state_code,
    process_plate,
    validate_plate,
)


class TestCleanPlateText:
    def test_remove_spaces(self):
        assert clean_plate_text("MH 12 AB 1234") == "MH12AB1234"

    def test_remove_hyphens(self):
        assert clean_plate_text("MH-12-AB-1234") == "MH12AB1234"

    def test_uppercase(self):
        assert clean_plate_text("mh12ab1234") == "MH12AB1234"

    def test_remove_special(self):
        assert clean_plate_text("MH.12.AB.1234!") == "MH12AB1234"


class TestValidatePlate:
    def test_standard_format(self):
        assert validate_plate("MH12AB1234") is True

    def test_single_letter_series(self):
        assert validate_plate("DL01A1234") is True

    def test_bh_series(self):
        assert validate_plate("22BH1234AB") is True

    def test_invalid_too_short(self):
        assert validate_plate("MH12") is False

    def test_invalid_all_letters(self):
        assert validate_plate("ABCDEFGH") is False

    def test_with_spaces(self):
        assert validate_plate("MH 12 AB 1234") is True

    def test_karnataka(self):
        assert validate_plate("KA01AB1234") is True

    def test_triple_letter(self):
        assert validate_plate("MH12ABC1234") is True


class TestCorrectOCRErrors:
    def test_zero_to_o_in_state(self):
        # "0H12AB1234" -> "OH12AB1234" (but OH isn't valid state)
        result = correct_ocr_errors("0H12AB1234")
        assert result[0] == "O"

    def test_o_to_zero_in_district(self):
        result = correct_ocr_errors("MHOOAB1234")
        assert result[2:4] == "00"

    def test_i_to_one_in_number(self):
        result = correct_ocr_errors("MH12ABI234")
        assert result[-4:] == "1234"

    def test_no_change_when_correct(self):
        result = correct_ocr_errors("MH12AB1234")
        assert result == "MH12AB1234"


class TestExtractStateCode:
    def test_maharashtra(self):
        assert extract_state_code("MH12AB1234") == "MH"

    def test_delhi(self):
        assert extract_state_code("DL01A1234") == "DL"

    def test_karnataka(self):
        assert extract_state_code("KA51AB1234") == "KA"

    def test_invalid(self):
        assert extract_state_code("XX12AB1234") is None

    def test_too_short(self):
        assert extract_state_code("M") is None


class TestProcessPlate:
    def test_full_pipeline(self):
        text, is_valid, state = process_plate("mh-12-ab-1234")
        assert text == "MH12AB1234"
        assert is_valid is True
        assert state == "MH"

    def test_invalid_plate(self):
        text, is_valid, state = process_plate("INVALID")
        assert is_valid is False
        assert state is None
