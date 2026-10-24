import pytest

from app.data_pipeline.parsing import parse_file


def test_parse_csv(tmp_path):
    """Test parsing a valid CSV file"""
    csv_content = "name,age,city\nAhmad,25,Amman\n"
    file_path = tmp_path / "sample.csv"
    file_path.write_text(csv_content)

    result = parse_file(str(file_path))

    assert result["columns"] == ["name", "age", "city"]
    assert result["row_count"] == 1


def test_parse_file_with_none_path():
    """Test that passing None raises a ValueError"""
    with pytest.raises(ValueError):
        parse_file(None)


def test_parse_file_with_empty_string():
    """Test that passing an empty string raises a ValueError"""
    with pytest.raises(ValueError):
        parse_file("")


def test_parse_file_with_unsupported_extension(tmp_path):
    """Test that an unsupported file extension raises a ValueError"""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("hello")

    with pytest.raises(ValueError):
        parse_file(str(file_path))
