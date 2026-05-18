from __future__ import annotations

from fractions import Fraction
import re

from .models import NoteEvent, Score, Track, TupletInfo


class DslParser:
    NOTE_RE = re.compile(
        r"(?P<step>[A-Ga-g])(?P<accidental>#|b)?(?P<octave>-?\d+)-(?P<duration>\d+)(?P<ornament>~(?:tr|trill))?",
        re.IGNORECASE,
    )
    TUPLET_RE = re.compile(
        r"T(?P<count>\d+)\[(?P<body>[^\]]+)\]-(?P<duration>\d+)",
        re.IGNORECASE,
    )
    TUPLET_PITCH_RE = re.compile(
        r"(?P<step>[A-Ga-g])(?P<accidental>#|b)?(?P<octave>-?\d+)(?P<ornament>~(?:tr|trill))?",
        re.IGNORECASE,
    )

    @classmethod
    def parse(cls, text: str) -> Score:
        score = Score()
        current_track: Track | None = None

        for line_number, line in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
            stripped = cls._strip_comment(line).strip()
            if not stripped:
                continue

            if stripped.startswith("@"):
                current_track = cls._parse_metadata(score, stripped, line_number, current_track)
                continue

            if current_track is None:
                raise ValueError(f"Line {line_number}: notes must appear after an @track metadata line.")

            cls._parse_music_line(stripped, current_track, line_number)

        cls._ensure_supported_metadata(score)
        score.get_or_create_track("RH")
        score.get_or_create_track("LH")
        return score

    @classmethod
    def _parse_metadata(
        cls,
        score: Score,
        line: str,
        line_number: int,
        current_track: Track | None,
    ) -> Track | None:
        if ":" not in line:
            raise ValueError(f"Line {line_number}: metadata must be written as @name: value.")

        name, value = line[1:].split(":", 1)
        name = name.strip().lower()
        value = value.strip()

        if name == "title":
            score.metadata.title = value
            return current_track
        if name == "unit":
            score.metadata.unit = value
            return current_track
        if name == "tempo":
            score.metadata.tempo_quarter_notes_per_minute = cls._parse_tempo(value, line_number)
            return current_track
        if name == "time":
            beats, beat_type = cls._parse_time(value, line_number)
            score.metadata.beats = beats
            score.metadata.beat_type = beat_type
            return current_track
        if name == "key":
            score.metadata.key = value
            return current_track
        if name == "track":
            if value.upper() not in {"RH", "LH"}:
                raise ValueError(f"Line {line_number}: supported tracks are RH and LH.")
            return score.get_or_create_track(value)

        raise ValueError(f"Line {line_number}: unsupported metadata '@{name}'.")

    @classmethod
    def _parse_music_line(cls, line: str, track: Track, line_number: int) -> None:
        segments = line.split(";")
        for index, segment in enumerate(segments):
            segment = segment.strip()
            if segment:
                cls._parse_slot_notes(segment, track, line_number)

            if index < len(segments) - 1:
                track.cursor_slot += 1

    @classmethod
    def _parse_slot_notes(cls, segment: str, track: Track, line_number: int) -> None:
        index = 0
        while index < len(segment):
            if segment[index].isspace():
                index += 1
                continue

            tuplet_match = cls.TUPLET_RE.match(segment, index)
            if tuplet_match is not None:
                cls._parse_tuplet(tuplet_match, track, line_number)
                index = tuplet_match.end()
                continue

            match = cls.NOTE_RE.match(segment, index)
            if match is None:
                near = segment[index:]
                raise ValueError(f"Line {line_number}: invalid note syntax near '{near}'.")

            step = match.group("step").upper()
            accidental = match.group("accidental") or ""
            alter = 1 if accidental == "#" else -1 if accidental == "b" else 0
            octave = int(match.group("octave"))
            duration = int(match.group("duration"))
            ornament = "trill" if match.group("ornament") else None
            if duration <= 0:
                raise ValueError(f"Line {line_number}: note duration must be greater than zero.")

            track.notes.append(
                NoteEvent(
                    step=step,
                    alter=alter,
                    octave=octave,
                    start_slot=Fraction(track.cursor_slot),
                    duration_slots=Fraction(duration),
                    track_name=track.name,
                    ornament=ornament,
                )
            )
            index = match.end()

    @classmethod
    def _parse_tuplet(cls, match: re.Match[str], track: Track, line_number: int) -> None:
        actual_notes = int(match.group("count"))
        if actual_notes != 3:
            raise NotImplementedError(f"Line {line_number}: only T3 triplets are currently supported.")

        duration = int(match.group("duration"))
        if duration <= 0:
            raise ValueError(f"Line {line_number}: tuplet duration must be greater than zero.")

        tokens = [token for token in re.split(r"[\s,]+", match.group("body").strip()) if token]
        if len(tokens) != actual_notes:
            raise ValueError(f"Line {line_number}: T3 must contain exactly 3 pitch tokens.")

        normal_notes = 2
        group_start = Fraction(track.cursor_slot)
        note_duration = Fraction(duration, actual_notes)
        normal_duration = Fraction(duration, normal_notes)

        for index, token in enumerate(tokens):
            pitch_match = cls.TUPLET_PITCH_RE.fullmatch(token)
            if pitch_match is None:
                raise ValueError(f"Line {line_number}: invalid tuplet pitch '{token}'.")

            step = pitch_match.group("step").upper()
            accidental = pitch_match.group("accidental") or ""
            alter = 1 if accidental == "#" else -1 if accidental == "b" else 0
            octave = int(pitch_match.group("octave"))
            ornament = "trill" if pitch_match.group("ornament") else None
            tuplet = TupletInfo(
                actual_notes=actual_notes,
                normal_notes=normal_notes,
                index=index,
                count=actual_notes,
                normal_duration_slots=normal_duration,
                group_start_slot=group_start,
            )

            track.notes.append(
                NoteEvent(
                    step=step,
                    alter=alter,
                    octave=octave,
                    start_slot=group_start + (note_duration * index),
                    duration_slots=note_duration,
                    track_name=track.name,
                    ornament=ornament,
                    tuplet=tuplet,
                )
            )

    @staticmethod
    def _parse_tempo(value: str, line_number: int) -> int:
        if not value.endswith("q") or not value[:-1].isdigit():
            raise ValueError(f"Line {line_number}: tempo must look like 120q.")
        tempo = int(value[:-1])
        if tempo <= 0:
            raise ValueError(f"Line {line_number}: tempo must be greater than zero.")
        return tempo

    @staticmethod
    def _parse_time(value: str, line_number: int) -> tuple[int, int]:
        parts = value.split("/")
        if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
            raise ValueError(f"Line {line_number}: time signature must look like 4/4.")
        beats, beat_type = int(parts[0]), int(parts[1])
        if beats <= 0 or beat_type <= 0:
            raise ValueError(f"Line {line_number}: time signature values must be greater than zero.")
        return beats, beat_type

    @staticmethod
    def _ensure_supported_metadata(score: Score) -> None:
        if score.metadata.unit != "1/16":
            raise NotImplementedError("Only @unit: 1/16 is supported.")
        if score.metadata.beats != 4 or score.metadata.beat_type != 4:
            raise NotImplementedError("Only @time: 4/4 is currently supported.")

    @staticmethod
    def _strip_comment(line: str) -> str:
        return line.split("//", 1)[0]
