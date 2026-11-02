"""Validated, atomic storage for local drafts and historical completions."""

import json
import os
import shutil
import tempfile
import time
from pathlib import Path


class ProgressStore:
    def __init__(self, path, exercise_ids):
        self.path = Path(path)
        self.exercise_ids = set(exercise_ids)
        self.warning = None
        self.save_blocked = None

    @staticmethod
    def empty():
        return {"drafts": {}, "solved": []}

    def load(self):
        self.warning = self.save_blocked = None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if (
                not isinstance(data, dict)
                or not isinstance(data.get("drafts", {}), dict)
                or not isinstance(data.get("solved", []), list)
                or any(
                    not isinstance(key, str) or not isinstance(value, str)
                    for key, value in data.get("drafts", {}).items()
                )
                or any(not isinstance(value, str) for value in data.get("solved", []))
            ):
                raise ValueError("Invalid progress format")
            # Unknown draft IDs are preserved; old completion IDs must not inflate the score.
            solved = list(
                dict.fromkeys(
                    value
                    for value in data.get("solved", [])
                    if value in self.exercise_ids
                )
            )
            return {"drafts": data.get("drafts", {}), "solved": solved}
        except FileNotFoundError:
            return self.empty()
        except (ValueError, UnicodeError) as error:
            backup = self.path.with_name(
                f"{self.path.stem}.corrupt-{time.time_ns()}{self.path.suffix}"
            )
            try:
                shutil.copy2(self.path, backup)
            except OSError as backup_error:
                self.save_blocked = (
                    f"Cannot back up the unreadable progress file: {backup_error}"
                )
                self.warning = f"{error}\n{self.save_blocked}\nSaving is disabled to protect the original file."
            else:
                self.warning = f"{error}\nThe original file is backed up at:\n{backup}\nStarting with empty progress."
            return self.empty()
        except OSError as error:
            self.save_blocked = f"Cannot read the existing progress file: {error}"
            self.warning = (
                f"{self.save_blocked}\nSaving is disabled to protect the original file."
            )
            return self.empty()

    def save(self, data):
        """Replace only after the entire new file has been written successfully."""
        if self.save_blocked:
            raise OSError(self.save_blocked)
        # Escaping also preserves unpaired surrogates accepted by Python's JSON decoder.
        content = json.dumps(data, indent=2, ensure_ascii=True)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as file:
                temporary = Path(file.name)
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
