"""Dependency-light OCR engine backed by the local Tesseract CLI."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable, Protocol

from PIL import Image


class OcrEngineError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OcrWord:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    block_num: int = 0
    paragraph_num: int = 0
    line_num: int = 0
    word_num: int = 0


@dataclass(frozen=True, slots=True)
class OcrResult:
    text: str
    words: tuple[OcrWord, ...]
    mean_confidence: float
    language: str
    page_segmentation_mode: int
    engine: str = "tesseract-cli"


class OcrEngine(Protocol):
    def recognize(
        self,
        image: Image.Image,
        *,
        language: str = "ita+eng",
        page_segmentation_mode: int = 11,
    ) -> OcrResult: ...


class TesseractCliEngine:
    def __init__(
        self,
        executable: str | Path | None = None,
        *,
        timeout_seconds: float = 20.0,
        runner: Callable = subprocess.run,
    ) -> None:
        self.executable = resolve_tesseract_executable(executable)
        self.timeout_seconds = float(timeout_seconds)
        self._runner = runner

    def recognize(
        self,
        image: Image.Image,
        *,
        language: str = "ita+eng",
        page_segmentation_mode: int = 11,
    ) -> OcrResult:
        if not language.strip():
            raise ValueError("OCR language is required")
        if not 0 <= int(page_segmentation_mode) <= 13:
            raise ValueError("Tesseract page segmentation mode must be between 0 and 13")
        payload = _image_to_png_bytes(image)
        command = [
            str(self.executable),
            "stdin",
            "stdout",
            "-l",
            language,
            "--psm",
            str(int(page_segmentation_mode)),
            "tsv",
        ]
        try:
            completed = self._runner(
                command,
                input=payload,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise OcrEngineError(f"Tesseract timed out after {self.timeout_seconds:g}s") from exc
        if completed.returncode != 0:
            stderr = _decode(completed.stderr).strip()
            raise OcrEngineError(f"Tesseract failed ({completed.returncode}): {stderr or 'no details'}")
        words = _parse_tesseract_tsv(_decode(completed.stdout))
        text = _words_to_text(words)
        mean = sum(word.confidence for word in words) / len(words) if words else 0.0
        return OcrResult(
            text=text,
            words=tuple(words),
            mean_confidence=round(mean, 4),
            language=language,
            page_segmentation_mode=int(page_segmentation_mode),
        )

    def health(self) -> dict[str, object]:
        try:
            completed = self._runner(
                [str(self.executable), "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=min(self.timeout_seconds, 5.0),
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ready": False, "executable": str(self.executable), "error": str(exc)}
        first_line = _decode(completed.stdout or completed.stderr).splitlines()
        return {
            "ready": completed.returncode == 0,
            "executable": str(self.executable),
            "version": first_line[0] if first_line else "",
        }


def resolve_tesseract_executable(executable: str | Path | None = None) -> Path:
    candidates = []
    if executable:
        candidates.append(Path(executable))
    env_value = os.environ.get("TESSERACT_EXE")
    if env_value:
        candidates.append(Path(env_value))
    which = shutil.which("tesseract")
    if which:
        candidates.append(Path(which))
    candidates.append(Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"))
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError("Tesseract executable not found; set TESSERACT_EXE or pass executable=")


def _image_to_png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _parse_tesseract_tsv(raw_tsv: str) -> list[OcrWord]:
    rows = raw_tsv.splitlines()
    if not rows:
        return []
    header = rows[0].split("\t")
    index = {name: position for position, name in enumerate(header)}
    required = {"left", "top", "width", "height", "conf", "text"}
    if not required.issubset(index):
        raise OcrEngineError("Tesseract TSV output is missing required columns")
    words = []
    for row in rows[1:]:
        columns = row.split("\t")
        if len(columns) < len(header):
            continue
        text = columns[index["text"]].strip()
        if not text:
            continue
        try:
            confidence = float(columns[index["conf"]])
            left = int(columns[index["left"]])
            top = int(columns[index["top"]])
            width = int(columns[index["width"]])
            height = int(columns[index["height"]])
        except ValueError:
            continue
        if confidence < 0:
            continue
        def optional_int(column: str) -> int:
            try:
                return int(columns[index[column]])
            except (KeyError, ValueError):
                return 0

        words.append(
            OcrWord(
                text,
                confidence,
                left,
                top,
                width,
                height,
                block_num=optional_int("block_num"),
                paragraph_num=optional_int("par_num"),
                line_num=optional_int("line_num"),
                word_num=optional_int("word_num"),
            )
        )
    return words


def _words_to_text(words: list[OcrWord]) -> str:
    lines: list[str] = []
    current_key = None
    current_words: list[str] = []
    for word in words:
        key = (word.block_num, word.paragraph_num, word.line_num)
        if current_key is not None and key != current_key:
            lines.append(" ".join(current_words))
            current_words = []
        current_key = key
        current_words.append(word.text)
    if current_words:
        lines.append(" ".join(current_words))
    return "\n".join(line for line in lines if line).strip()


def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


__all__ = [
    "OcrEngine",
    "OcrEngineError",
    "OcrResult",
    "OcrWord",
    "TesseractCliEngine",
    "resolve_tesseract_executable",
]
