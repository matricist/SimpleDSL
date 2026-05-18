from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .models import NoteEvent, Score


DIVISIONS = 4
MEASURE_SLOTS = 16
PART_IDS = {"RH": "P1", "LH": "P2"}
PART_NAMES = {"RH": "Right Hand", "LH": "Left Hand"}
NOTE_CHUNK_SIZES = (16, 12, 8, 6, 4, 3, 2, 1)
NOTE_TYPES = {
    16: ("whole", 0),
    12: ("half", 1),
    8: ("half", 0),
    6: ("quarter", 1),
    4: ("quarter", 0),
    3: ("eighth", 1),
    2: ("eighth", 0),
    1: ("16th", 0),
}
KEY_FIFTHS = {
    "Cb": -7,
    "Gb": -6,
    "Db": -5,
    "Ab": -4,
    "Eb": -3,
    "Bb": -2,
    "F": -1,
    "C": 0,
    "G": 1,
    "D": 2,
    "A": 3,
    "E": 4,
    "B": 5,
    "F#": 6,
    "C#": 7,
}


@dataclass(frozen=True)
class NoteChunk:
    note: NoteEvent
    start_slot: int
    duration_slots: int

    @property
    def end_slot(self) -> int:
        return self.start_slot + self.duration_slots

    @property
    def tie_stop(self) -> bool:
        return self.start_slot > self.note.start_slot

    @property
    def tie_start(self) -> bool:
        return self.end_slot < self.note.end_slot


class MusicXmlExporter:
    @classmethod
    def export(cls, score: Score) -> str:
        lines: list[str] = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">',
            '<score-partwise version="4.0">',
            f"  <work><work-title>{escape(score.metadata.title)}</work-title></work>",
            "  <part-list>",
        ]

        for track_name in ("RH", "LH"):
            part_id = PART_IDS[track_name]
            part_name = PART_NAMES[track_name]
            lines.extend(
                [
                    f'    <score-part id="{part_id}">',
                    f"      <part-name>{part_name}</part-name>",
                    f'      <score-instrument id="{part_id}-I1">',
                    "        <instrument-name>Harpsichord</instrument-name>",
                    "      </score-instrument>",
                    f'      <midi-instrument id="{part_id}-I1">',
                    "        <midi-program>7</midi-program>",
                    "      </midi-instrument>",
                    "    </score-part>",
                ]
            )

        lines.append("  </part-list>")
        for track_name in ("RH", "LH"):
            cls._append_part(lines, score, track_name)
        lines.append("</score-partwise>")
        return "\n".join(lines) + "\n"

    @classmethod
    def _append_part(cls, lines: list[str], score: Score, track_name: str) -> None:
        track = score.get_or_create_track(track_name)
        measure_count = max(1, (track.end_slot + MEASURE_SLOTS - 1) // MEASURE_SLOTS)

        lines.append(f'  <part id="{PART_IDS[track_name]}">')
        for measure_number in range(1, measure_count + 1):
            measure_start = (measure_number - 1) * MEASURE_SLOTS
            measure_end = measure_start + MEASURE_SLOTS
            lines.append(f'    <measure number="{measure_number}">')

            if measure_number == 1:
                cls._append_attributes(lines, score, track_name)
                cls._append_tempo(lines, score)

            cls._append_measure_contents(lines, track.notes, measure_start, measure_end)
            lines.append("    </measure>")

        lines.append("  </part>")

    @classmethod
    def _append_attributes(cls, lines: list[str], score: Score, track_name: str) -> None:
        fifths = KEY_FIFTHS.get(score.metadata.key.strip(), 0)
        clef_sign, clef_line = ("F", 4) if track_name == "LH" else ("G", 2)
        lines.extend(
            [
                "      <attributes>",
                f"        <divisions>{DIVISIONS}</divisions>",
                "        <key>",
                f"          <fifths>{fifths}</fifths>",
                "        </key>",
                "        <time>",
                f"          <beats>{score.metadata.beats}</beats>",
                f"          <beat-type>{score.metadata.beat_type}</beat-type>",
                "        </time>",
                "        <clef>",
                f"          <sign>{clef_sign}</sign>",
                f"          <line>{clef_line}</line>",
                "        </clef>",
                "      </attributes>",
            ]
        )

    @staticmethod
    def _append_tempo(lines: list[str], score: Score) -> None:
        tempo = score.metadata.tempo_quarter_notes_per_minute
        lines.append(
            '      <direction placement="above"><direction-type><metronome>'
            f"<beat-unit>quarter</beat-unit><per-minute>{tempo}</per-minute>"
            f'</metronome></direction-type><sound tempo="{tempo}"/></direction>'
        )

    @classmethod
    def _append_measure_contents(
        cls,
        lines: list[str],
        notes: list[NoteEvent],
        measure_start: int,
        measure_end: int,
    ) -> None:
        chunks = [
            chunk
            for note in notes
            if note.start_slot < measure_end and note.end_slot > measure_start
            for chunk in cls._split_note(note, measure_start, measure_end)
        ]
        groups: dict[int, list[NoteChunk]] = {}
        for chunk in chunks:
            groups.setdefault(chunk.start_slot, []).append(chunk)

        cursor = measure_start
        for start_slot in sorted(groups):
            if start_slot > cursor:
                cls._append_rest_range(lines, cursor, start_slot)

            ordered = sorted(
                groups[start_slot],
                key=lambda chunk: (-chunk.duration_slots, chunk.note.step, chunk.note.octave),
            )
            for index, chunk in enumerate(ordered):
                cls._append_pitched_note(lines, chunk, chord=index > 0)

            cursor = max(cursor, max(chunk.end_slot for chunk in ordered))

        if cursor < measure_end:
            cls._append_rest_range(lines, cursor, measure_end)

    @classmethod
    def _split_note(cls, note: NoteEvent, measure_start: int, measure_end: int) -> list[NoteChunk]:
        start = max(note.start_slot, measure_start)
        end = min(note.end_slot, measure_end)
        chunks: list[NoteChunk] = []

        while start < end:
            boundary = min(end, ((start // MEASURE_SLOTS) + 1) * MEASURE_SLOTS)
            remaining = boundary - start
            duration = cls._best_chunk_size(remaining)
            chunks.append(NoteChunk(note, start, duration))
            start += duration

        return chunks

    @staticmethod
    def _best_chunk_size(remaining_slots: int) -> int:
        for size in NOTE_CHUNK_SIZES:
            if size <= remaining_slots:
                return size
        raise ValueError(f"Cannot represent duration of {remaining_slots} slots.")

    @classmethod
    def _append_rest_range(cls, lines: list[str], start_slot: int, end_slot: int) -> None:
        cursor = start_slot
        while cursor < end_slot:
            duration = cls._best_chunk_size(end_slot - cursor)
            cls._append_rest(lines, duration)
            cursor += duration

    @classmethod
    def _append_pitched_note(cls, lines: list[str], chunk: NoteChunk, chord: bool) -> None:
        note_type, dot_count = NOTE_TYPES[chunk.duration_slots]
        lines.append("      <note>")
        if chord:
            lines.append("        <chord/>")
        lines.extend(
            [
                "        <pitch>",
                f"          <step>{chunk.note.step}</step>",
            ]
        )
        if chunk.note.alter:
            lines.append(f"          <alter>{chunk.note.alter}</alter>")
        lines.extend(
            [
                f"          <octave>{chunk.note.octave}</octave>",
                "        </pitch>",
                f"        <duration>{chunk.duration_slots}</duration>",
            ]
        )
        if chunk.tie_stop:
            lines.append('        <tie type="stop"/>')
        if chunk.tie_start:
            lines.append('        <tie type="start"/>')
        lines.append(f"        <type>{note_type}</type>")
        for _ in range(dot_count):
            lines.append("        <dot/>")
        if chunk.tie_stop or chunk.tie_start:
            lines.append("        <notations>")
            if chunk.tie_stop:
                lines.append('          <tied type="stop"/>')
            if chunk.tie_start:
                lines.append('          <tied type="start"/>')
            lines.append("        </notations>")
        lines.append("      </note>")

    @classmethod
    def _append_rest(cls, lines: list[str], duration: int) -> None:
        note_type, dot_count = NOTE_TYPES[duration]
        lines.extend(
            [
                "      <note>",
                "        <rest/>",
                f"        <duration>{duration}</duration>",
                f"        <type>{note_type}</type>",
            ]
        )
        for _ in range(dot_count):
            lines.append("        <dot/>")
        lines.append("      </note>")
