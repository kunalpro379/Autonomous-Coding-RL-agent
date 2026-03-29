from __future__ import annotations

from pathlib import Path

from config.settings import settings


class FileTools:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or settings.workspace_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe(self, rel: str) -> Path:
        target = (self.root / rel).resolve()
        if self.root not in target.parents and target != self.root:
            raise ValueError("path_escape")
        return target

    def read_file(self, rel: str) -> str:
        p = self._safe(rel)
        if not p.is_file():
            raise FileNotFoundError(rel)
        return p.read_text(encoding="utf-8", errors="replace")

    def write_file(self, rel: str, content: str) -> str:
        p = self._safe(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return str(p)

    def list_dir(self, rel: str = ".") -> list[str]:
        d = self._safe(rel)
        if not d.is_dir():
            raise NotADirectoryError(rel)
        return sorted(str(x.relative_to(self.root)).replace("\\", "/") for x in d.iterdir())

    # --- richer edit operations for agents ---

    def read_lines(self, rel: str) -> list[str]:
        """Return file as list of lines (keeps trailing newlines)."""
        text = self.read_file(rel)
        return text.splitlines(keepends=True)

    def write_lines(self, rel: str, lines: list[str]) -> str:
        """Overwrite file with given list of lines."""
        return self.write_file(rel, "".join(lines))

    def update_line_span(
        self,
        rel: str,
        start_line: int,
        end_line: int,
        new_block: str,
    ) -> str:
        """
        Replace lines [start_line, end_line] (1-based, inclusive) with new_block.
        new_block can contain multiple lines.
        """
        lines = self.read_lines(rel)
        n = len(lines)
        if not (1 <= start_line <= n + 1) or not (start_line <= end_line <= n):
            raise IndexError("invalid line span")
        # Convert to 0-based indices
        s = start_line - 1
        e = end_line
        replacement = new_block.splitlines(keepends=True)
        if new_block and not new_block.endswith(("\n", "\r\n")):
            replacement[-1] = replacement[-1] + "\n"
        new_lines = lines[:s] + replacement + lines[e:]
        return self.write_lines(rel, new_lines)

    def update_char_span(
        self,
        rel: str,
        start_offset: int,
        end_offset: int,
        new_text: str,
    ) -> str:
        """
        Replace characters in [start_offset, end_offset) (0-based) with new_text.
        Useful when the model knows exact char indices.
        """
        text = self.read_file(rel)
        n = len(text)
        if not (0 <= start_offset <= end_offset <= n):
            raise IndexError("invalid char span")
        updated = text[:start_offset] + new_text + text[end_offset:]
        return self.write_file(rel, updated)