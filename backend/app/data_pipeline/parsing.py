from abc import ABC, abstractmethod

import pandas as pd

from app.shared.file_utils import get_extension


class BaseParser(ABC):
    """Base class for all file parsers"""

    @abstractmethod
    def parse(self, file_path: str) -> pd.DataFrame:
        pass


class CSVParser(BaseParser):
    """Parser for CSV files with common encoding support."""

    ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin1")

    def parse(self, file_path: str) -> pd.DataFrame:
        last_error = None

        for encoding in self.ENCODINGS:
            try:
                return pd.read_csv(file_path, encoding=encoding)
            except UnicodeDecodeError as exc:
                last_error = exc

        raise ValueError(
            f"Could not decode CSV file using supported encodings: {', '.join(self.ENCODINGS)}"
        ) from last_error


class ExcelParser(BaseParser):
    """Parser for Excel files"""

    def parse(self, file_path: str) -> pd.DataFrame:
        return pd.read_excel(file_path)


class ParserFactory:
    """Factory that returns the correct parser based on file extension"""

    _parsers = {
        ".csv": CSVParser,
        ".xlsx": ExcelParser,
        ".xls": ExcelParser,
    }

    @classmethod
    def get_parser(cls, file_path: str) -> BaseParser:
        if not isinstance(file_path, str) or not file_path.strip():
            raise ValueError("file_path must be a non-empty string")

        ext = get_extension(file_path)

        parser_class = cls._parsers.get(ext)

        if parser_class is None:
            raise ValueError(f"Unsupported file type: {ext}")

        return parser_class()


def extract_columns_and_rows(df: pd.DataFrame) -> dict:
    """Extract column names and rows into a structured format"""
    return {
        "columns": list(df.columns),
        "row_count": len(df),
        "rows": df.to_dict(orient="records"),
        "dataframe": df,
    }


def parse_file(file_path: str) -> dict:
    """Parse a CSV or Excel file and return a unified result"""
    parser = ParserFactory.get_parser(file_path)
    df = parser.parse(file_path)

    return extract_columns_and_rows(df)
