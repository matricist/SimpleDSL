from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from html import escape

from .models import ChordSymbol, NoteEvent, Score


DIVISIONS = 12
SLOT_DURATION_UNITS = DIVISIONS // 4
MEASURE_SLOTS = 16
PART_IDS = {"RH": "P1", "LH": "P2"}
PART_NAMES = {"RH": "Right Hand", "LH": "Left Hand"}
NOTE_CHUNK_SIZES = tuple(Fraction(size) for size in (16, 12, 8, 6, 4, 3, 2, 1))
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
    start_slot: Fraction
    duration_slots: Fraction

    @property
    def end_slot(self) -> Fraction:
        return self.start_slot + self.duration_slots

    @property
    def tie_stop(self) -> bool:
        return self.start_slot > self.note.start_slot

    @property
    def tie_start(self) -> bool:
        return self.end_slot < self.note.end_slot

    @property
    def has_start_ornament(self) -> bool:
        return self.note.ornament is not None and self.start_slot == self.note.start_slot


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
        measure_count = max(1, cls._ceil_slot(track.end_slot, MEASURE_SLOTS))

        lines.append(f'  <part id="{PART_IDS[track_name]}">')
        for measure_number in range(1, measure_count + 1):
            measure_start = (measure_number - 1) * MEASURE_SLOTS
            measure_end = measure_start + MEASURE_SLOTS
            lines.append(f'    <measure number="{measure_number}">')

            if measure_number == 1:
                cls._append_attributes(lines, score, track_name)
                cls._append_tempo(lines, score)

            cls._append_measure_contents(lines, track.notes, track.chord_symbols, measure_start, measure_end)
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
        chord_symbols: list[ChordSymbol],
        measure_start: int,
        measure_end: int,
    ) -> None:
        chunks = [
            chunk
            for note in notes
            if note.start_slot < measure_end and note.end_slot > measure_start
            for chunk in cls._split_note(note, measure_start, measure_end)
        ]
        groups: dict[Fraction, list[NoteChunk]] = {}
        for chunk in chunks:
            groups.setdefault(chunk.start_slot, []).append(chunk)

        chords: dict[Fraction, list[ChordSymbol]] = {}
        for chord in chord_symbols:
            if measure_start <= chord.start_slot < measure_end:
                chords.setdefault(chord.start_slot, []).append(chord)

        beams = cls._calculate_beams(groups, measure_start, measure_end)
        cursor = Fraction(measure_start)
        for start_slot in sorted(set(groups) | set(chords)):
            if start_slot > cursor:
                cls._append_rest_range(lines, cursor, start_slot)

            for chord in chords.get(start_slot, []):
                cls._append_chord_symbol(lines, chord)

            if start_slot not in groups:
                continue

            ordered = sorted(
                groups[start_slot],
                key=lambda chunk: (-chunk.duration_slots, chunk.note.step, chunk.note.octave),
            )
            for index, chunk in enumerate(ordered):
                cls._append_pitched_note(
                    lines,
                    chunk,
                    chord=index > 0,
                    beams=beams.get(start_slot) if index == 0 else None,
                )

            cursor = max(cursor, max(chunk.end_slot for chunk in ordered))

        if cursor < measure_end:
            cls._append_rest_range(lines, cursor, measure_end)

    @staticmethod
    def _append_chord_symbol(lines: list[str], chord: ChordSymbol) -> None:
        lines.extend(
            [
                "      <harmony>",
                "        <root>",
                f"          <root-step>{chord.root_step}</root-step>",
            ]
        )
        if chord.root_alter:
            lines.append(f"          <root-alter>{chord.root_alter}</root-alter>")
        lines.extend(
            [
                "        </root>",
                f'        <kind text="{escape(chord.kind_text)}">{chord.kind}</kind>',
            ]
        )
        if chord.bass_step is not None:
            lines.extend(
                [
                    "        <bass>",
                    f"          <bass-step>{chord.bass_step}</bass-step>",
                ]
            )
            if chord.bass_alter:
                lines.append(f"          <bass-alter>{chord.bass_alter}</bass-alter>")
            lines.extend(
                [
                    "        </bass>",
                ]
            )
        lines.append("      </harmony>")

    @classmethod
    def _calculate_beams(
        cls,
        groups: dict[Fraction, list[NoteChunk]],
        measure_start: int,
        measure_end: int,
    ) -> dict[Fraction, dict[int, str]]:
        beams: dict[Fraction, dict[int, str]] = {}

        for beat_start in range(measure_start, measure_end, 4):
            beat_end = min(beat_start + 4, measure_end)
            starts = sorted(start for start in groups if beat_start <= start < beat_end)
            index = 0

            while index < len(starts):
                start_index = index
                cursor = starts[index]
                run: list[tuple[Fraction, Fraction]] = []

                while index < len(starts):
                    start = starts[index]
                    duration = cls._beamable_group_duration(groups[start])
                    if start != cursor or duration is None or start + duration > beat_end:
                        break

                    run.append((start, duration))
                    cursor = start + duration
                    index += 1

                if len(run) >= 2:
                    cls._assign_beam_run(beams, run)

                if index == start_index:
                    index += 1

        cls._assign_tuplet_beams(beams, groups)
        return beams

    @staticmethod
    def _beamable_group_duration(chunks: list[NoteChunk]) -> Fraction | None:
        durations = {chunk.duration_slots for chunk in chunks}
        if len(durations) != 1:
            return None

        duration = next(iter(durations))
        return duration if duration in {Fraction(1), Fraction(2)} else None

    @staticmethod
    def _assign_beam_run(beams: dict[Fraction, dict[int, str]], run: list[tuple[Fraction, Fraction]]) -> None:
        for index, (start, _) in enumerate(run):
            if index == 0:
                value = "begin"
            elif index == len(run) - 1:
                value = "end"
            else:
                value = "continue"

            beams[start] = {1: value}

        sixteenth_runs: list[list[tuple[Fraction, Fraction]]] = []
        current: list[tuple[Fraction, Fraction]] = []
        for item in run:
            if item[1] == 1:
                current.append(item)
                continue

            if current:
                sixteenth_runs.append(current)
                current = []

        if current:
            sixteenth_runs.append(current)

        for sixteenth_run in sixteenth_runs:
            if len(sixteenth_run) == 1:
                start = sixteenth_run[0][0]
                run_index = next(index for index, item in enumerate(run) if item[0] == start)
                beams[start][2] = "forward hook" if run_index == 0 else "backward hook"
                continue

            for index, (start, _) in enumerate(sixteenth_run):
                if index == 0:
                    value = "begin"
                elif index == len(sixteenth_run) - 1:
                    value = "end"
                else:
                    value = "continue"

                beams[start][2] = value

    @classmethod
    def _assign_tuplet_beams(
        cls,
        beams: dict[Fraction, dict[int, str]],
        groups: dict[Fraction, list[NoteChunk]],
    ) -> None:
        tuplet_runs: dict[tuple[Fraction, int, int], list[NoteChunk]] = {}
        for chunks in groups.values():
            for chunk in chunks:
                if chunk.note.tuplet is None:
                    continue
                tuplet = chunk.note.tuplet
                key = (tuplet.group_start_slot, tuplet.actual_notes, tuplet.normal_notes)
                tuplet_runs.setdefault(key, []).append(chunk)

        for run in tuplet_runs.values():
            ordered = sorted(run, key=lambda chunk: chunk.note.tuplet.index if chunk.note.tuplet else 0)
            if len(ordered) < 2:
                continue

            for index, chunk in enumerate(ordered):
                if index == 0:
                    value = "begin"
                elif index == len(ordered) - 1:
                    value = "end"
                else:
                    value = "continue"

                beams.setdefault(chunk.start_slot, {})[1] = value
                if cls._note_type_for_slots(chunk.note.tuplet.normal_duration_slots)[0] == "16th":
                    beams[chunk.start_slot][2] = value

    @classmethod
    def _split_note(cls, note: NoteEvent, measure_start: int, measure_end: int) -> list[NoteChunk]:
        note_start = Fraction(note.start_slot)
        note_end = Fraction(note.end_slot)
        if note.tuplet is not None:
            if note_start < measure_start or note_end > measure_end:
                raise ValueError("Tuplet notes cannot cross a measure boundary.")
            return [NoteChunk(note, note_start, note.duration_slots)]

        start = max(note_start, Fraction(measure_start))
        end = min(note_end, Fraction(measure_end))
        chunks: list[NoteChunk] = []

        while start < end:
            boundary = min(end, Fraction(((int(start) // MEASURE_SLOTS) + 1) * MEASURE_SLOTS))
            remaining = boundary - start
            duration = cls._best_chunk_size(remaining)
            chunks.append(NoteChunk(note, start, duration))
            start += duration

        return chunks

    @staticmethod
    def _best_chunk_size(remaining_slots: Fraction) -> Fraction:
        for size in NOTE_CHUNK_SIZES:
            if size <= remaining_slots:
                return size
        raise ValueError(f"Cannot represent duration of {remaining_slots} slots.")

    @classmethod
    def _append_rest_range(cls, lines: list[str], start_slot: Fraction, end_slot: Fraction) -> None:
        if start_slot.denominator != 1 or end_slot.denominator != 1:
            raise ValueError("Cannot create rests on fractional tuplet boundaries.")

        cursor = start_slot
        while cursor < end_slot:
            duration = cls._best_chunk_size(end_slot - cursor)
            cls._append_rest(lines, duration)
            cursor += duration

    @classmethod
    def _append_pitched_note(
        cls,
        lines: list[str],
        chunk: NoteChunk,
        chord: bool,
        beams: dict[int, str] | None = None,
    ) -> None:
        visual_duration = (
            chunk.note.tuplet.normal_duration_slots
            if chunk.note.tuplet is not None
            else chunk.duration_slots
        )
        note_type, dot_count = cls._note_type_for_slots(visual_duration)
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
                f"        <duration>{cls._duration_units(chunk.duration_slots)}</duration>",
            ]
        )
        if chunk.tie_stop:
            lines.append('        <tie type="stop"/>')
        if chunk.tie_start:
            lines.append('        <tie type="start"/>')
        lines.append(f"        <type>{note_type}</type>")
        for _ in range(dot_count):
            lines.append("        <dot/>")
        if chunk.note.tuplet is not None:
            lines.extend(
                [
                    "        <time-modification>",
                    f"          <actual-notes>{chunk.note.tuplet.actual_notes}</actual-notes>",
                    f"          <normal-notes>{chunk.note.tuplet.normal_notes}</normal-notes>",
                    "        </time-modification>",
                ]
            )
        if beams:
            for number, value in sorted(beams.items()):
                lines.append(f'        <beam number="{number}">{value}</beam>')
        has_notations = chunk.tie_stop or chunk.tie_start or chunk.has_start_ornament or chunk.note.tuplet is not None
        if has_notations:
            lines.append("        <notations>")
            if chunk.tie_stop:
                lines.append('          <tied type="stop"/>')
            if chunk.tie_start:
                lines.append('          <tied type="start"/>')
            if chunk.has_start_ornament:
                cls._append_ornament(lines, chunk.note.ornament)
            if chunk.note.tuplet is not None:
                cls._append_tuplet(lines, chunk.note.tuplet.index, chunk.note.tuplet.count)
            lines.append("        </notations>")
        lines.append("      </note>")

    @staticmethod
    def _append_ornament(lines: list[str], ornament: str | None) -> None:
        if ornament == "trill":
            lines.extend(
                [
                    "          <ornaments>",
                    "            <trill-mark/>",
                    "          </ornaments>",
                ]
            )

    @staticmethod
    def _append_tuplet(lines: list[str], index: int, count: int) -> None:
        if index == 0:
            lines.append('          <tuplet type="start" bracket="yes"/>')
        if index == count - 1:
            lines.append('          <tuplet type="stop"/>')

    @classmethod
    def _append_rest(cls, lines: list[str], duration: Fraction) -> None:
        note_type, dot_count = cls._note_type_for_slots(duration)
        lines.extend(
            [
                "      <note>",
                "        <rest/>",
                f"        <duration>{cls._duration_units(duration)}</duration>",
                f"        <type>{note_type}</type>",
            ]
        )
        for _ in range(dot_count):
            lines.append("        <dot/>")
        lines.append("      </note>")

    @staticmethod
    def _ceil_slot(value: Fraction, slots_per_measure: int) -> int:
        value = Fraction(value)
        denominator = value.denominator * slots_per_measure
        return (value.numerator + denominator - 1) // denominator

    @staticmethod
    def _duration_units(duration_slots: Fraction) -> int:
        units = Fraction(duration_slots) * SLOT_DURATION_UNITS
        if units.denominator != 1:
            raise ValueError(f"Cannot represent duration of {duration_slots} slots with divisions={DIVISIONS}.")
        return units.numerator

    @staticmethod
    def _note_type_for_slots(duration_slots: Fraction) -> tuple[str, int]:
        duration_slots = Fraction(duration_slots)
        if duration_slots.denominator != 1:
            raise ValueError(f"Cannot infer note type for fractional duration {duration_slots} slots.")
        try:
            return NOTE_TYPES[duration_slots.numerator]
        except KeyError as exc:
            raise ValueError(f"Cannot represent duration of {duration_slots} slots.") from exc
