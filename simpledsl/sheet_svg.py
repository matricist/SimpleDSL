from __future__ import annotations

from dataclasses import dataclass
from html import escape

from .models import NoteEvent, Score, Track


MEASURE_SLOTS = 16
MEASURES_PER_SYSTEM = 4
PAGE_WIDTH = 1180
MARGIN_LEFT = 72
MARGIN_TOP = 72
MEASURE_WIDTH = 250
STAFF_LINE_SPACING = 10
STAFF_GAP = 86
SYSTEM_GAP = 190
STEP_OFFSETS = {"C": 0, "D": 1, "E": 2, "F": 3, "G": 4, "A": 5, "B": 6}


@dataclass(frozen=True)
class DrawSegment:
    note: NoteEvent
    start_slot: int
    end_slot: int

    @property
    def duration_slots(self) -> int:
        return self.end_slot - self.start_slot


class SheetSvgExporter:
    @classmethod
    def export(cls, score: Score) -> str:
        max_end = max((track.end_slot for track in score.tracks.values()), default=0)
        measure_count = max(1, (max_end + MEASURE_SLOTS - 1) // MEASURE_SLOTS)
        system_count = (measure_count + MEASURES_PER_SYSTEM - 1) // MEASURES_PER_SYSTEM
        page_height = MARGIN_TOP + 70 + system_count * SYSTEM_GAP + 40

        lines = [
            '<?xml version="1.0" encoding="UTF-8"?>',
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{PAGE_WIDTH}" height="{page_height}" viewBox="0 0 {PAGE_WIDTH} {page_height}">',
            '  <rect width="100%" height="100%" fill="#fffdf8"/>',
            f'  <text x="{PAGE_WIDTH / 2:g}" y="42" text-anchor="middle" font-family="Georgia, serif" font-size="26" fill="#1f2933">{escape(score.metadata.title)}</text>',
            f'  <text x="{PAGE_WIDTH / 2:g}" y="66" text-anchor="middle" font-family="Arial, sans-serif" font-size="13" fill="#52606d">{escape(score.metadata.key)} · {score.metadata.beats}/{score.metadata.beat_type} · {score.metadata.tempo_quarter_notes_per_minute} BPM</text>',
        ]

        for system_index in range(system_count):
            first_measure = system_index * MEASURES_PER_SYSTEM
            measures_in_system = min(MEASURES_PER_SYSTEM, measure_count - first_measure)
            system_y = MARGIN_TOP + 50 + system_index * SYSTEM_GAP
            cls._draw_system(lines, score, first_measure, measures_in_system, system_y)

        lines.append("</svg>")
        return "\n".join(lines) + "\n"

    @classmethod
    def _draw_system(
        cls,
        lines: list[str],
        score: Score,
        first_measure: int,
        measures_in_system: int,
        system_y: float,
    ) -> None:
        treble_top = system_y
        bass_top = system_y + STAFF_GAP
        left = MARGIN_LEFT
        right = MARGIN_LEFT + measures_in_system * MEASURE_WIDTH

        cls._draw_staff(lines, left, right, treble_top)
        cls._draw_staff(lines, left, right, bass_top)
        lines.append(
            f'  <path d="M {left - 10:g} {treble_top:g} C {left - 34:g} {treble_top + 24:g}, {left - 34:g} {bass_top - 20:g}, {left - 14:g} {(treble_top + bass_top + 40) / 2:g} C {left - 34:g} {bass_top + 62:g}, {left - 34:g} {bass_top + 16:g}, {left - 10:g} {bass_top + 40:g}" fill="none" stroke="#1f2933" stroke-width="2"/>'
        )
        lines.append(f'  <text x="{left - 44:g}" y="{treble_top + 25:g}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#52606d">RH</text>')
        lines.append(f'  <text x="{left - 44:g}" y="{bass_top + 25:g}" text-anchor="middle" font-family="Arial, sans-serif" font-size="12" fill="#52606d">LH</text>')
        lines.append(f'  <text x="{left - 12:g}" y="{treble_top + 31:g}" text-anchor="middle" font-family="Georgia, serif" font-size="36" fill="#1f2933">𝄞</text>')
        lines.append(f'  <text x="{left - 12:g}" y="{bass_top + 32:g}" text-anchor="middle" font-family="Georgia, serif" font-size="34" fill="#1f2933">𝄢</text>')

        for offset in range(measures_in_system + 1):
            x = left + offset * MEASURE_WIDTH
            lines.append(f'  <line x1="{x:g}" y1="{treble_top:g}" x2="{x:g}" y2="{treble_top + STAFF_LINE_SPACING * 4:g}" stroke="#1f2933" stroke-width="1"/>')
            lines.append(f'  <line x1="{x:g}" y1="{bass_top:g}" x2="{x:g}" y2="{bass_top + STAFF_LINE_SPACING * 4:g}" stroke="#1f2933" stroke-width="1"/>')
            if offset < measures_in_system:
                lines.append(f'  <text x="{x + 8:g}" y="{treble_top - 10:g}" font-family="Arial, sans-serif" font-size="11" fill="#6b7280">{first_measure + offset + 1}</text>')

        cls._draw_track(lines, score.get_or_create_track("RH"), first_measure, measures_in_system, treble_top, is_bass=False)
        cls._draw_track(lines, score.get_or_create_track("LH"), first_measure, measures_in_system, bass_top, is_bass=True)

    @staticmethod
    def _draw_staff(lines: list[str], left: float, right: float, top: float) -> None:
        for line_index in range(5):
            y = top + line_index * STAFF_LINE_SPACING
            lines.append(f'  <line x1="{left:g}" y1="{y:g}" x2="{right:g}" y2="{y:g}" stroke="#1f2933" stroke-width="1"/>')

    @classmethod
    def _draw_track(
        cls,
        lines: list[str],
        track: Track,
        first_measure: int,
        measures_in_system: int,
        staff_top: float,
        is_bass: bool,
    ) -> None:
        for measure_offset in range(measures_in_system):
            measure_number = first_measure + measure_offset
            measure_start = measure_number * MEASURE_SLOTS
            measure_end = measure_start + MEASURE_SLOTS
            measure_left = MARGIN_LEFT + measure_offset * MEASURE_WIDTH

            segments = [
                DrawSegment(note, max(note.start_slot, measure_start), min(note.end_slot, measure_end))
                for note in track.notes
                if note.start_slot < measure_end and note.end_slot > measure_start
            ]
            groups: dict[int, list[DrawSegment]] = {}
            for segment in segments:
                groups.setdefault(segment.start_slot, []).append(segment)

            cursor = measure_start
            for start_slot in sorted(groups):
                if start_slot > cursor:
                    cls._draw_rest(lines, measure_left, staff_top, start_slot - measure_start)

                ordered = sorted(groups[start_slot], key=lambda segment: cls._pitch_y(segment.note, staff_top, is_bass))
                for chord_index, segment in enumerate(ordered):
                    cls._draw_note(lines, measure_left, staff_top, segment, is_bass, chord_index)
                cursor = max(cursor, max(segment.end_slot for segment in ordered))

            if cursor < measure_end:
                cls._draw_rest(lines, measure_left, staff_top, cursor - measure_start)

    @classmethod
    def _draw_note(
        cls,
        lines: list[str],
        measure_left: float,
        staff_top: float,
        segment: DrawSegment,
        is_bass: bool,
        chord_index: int,
    ) -> None:
        x = cls._slot_x(measure_left, segment.start_slot % MEASURE_SLOTS) + chord_index * 4
        y = cls._pitch_y(segment.note, staff_top, is_bass)
        stem_up = y >= staff_top + STAFF_LINE_SPACING * 2
        stem_x = x + 6 if stem_up else x - 6
        stem_end_y = y - 34 if stem_up else y + 34
        fill = "#1f2933" if segment.duration_slots <= 8 else "#fffdf8"

        cls._draw_ledger_lines(lines, x, y, staff_top)
        lines.append(f'  <ellipse cx="{x:g}" cy="{y:g}" rx="7" ry="5" transform="rotate(-18 {x:g} {y:g})" fill="{fill}" stroke="#1f2933" stroke-width="1.5"/>')
        lines.append(f'  <line x1="{stem_x:g}" y1="{y:g}" x2="{stem_x:g}" y2="{stem_end_y:g}" stroke="#1f2933" stroke-width="1.5"/>')

        if segment.start_slot > segment.note.start_slot:
            lines.append(f'  <path d="M {x - 18:g} {y + 14:g} Q {x:g} {y + 24:g} {x + 18:g} {y + 14:g}" fill="none" stroke="#1f2933" stroke-width="1"/>')
        if segment.end_slot < segment.note.end_slot:
            lines.append(f'  <path d="M {x + 10:g} {y + 14:g} Q {x + 29:g} {y + 24:g} {x + 48:g} {y + 14:g}" fill="none" stroke="#1f2933" stroke-width="1"/>')

    @staticmethod
    def _draw_rest(lines: list[str], measure_left: float, staff_top: float, start_offset: int) -> None:
        x = SheetSvgExporter._slot_x(measure_left, start_offset)
        y = staff_top + STAFF_LINE_SPACING * 2
        lines.append(f'  <text x="{x:g}" y="{y + 7:g}" text-anchor="middle" font-family="Georgia, serif" font-size="20" fill="#52606d">𝄽</text>')

    @staticmethod
    def _draw_ledger_lines(lines: list[str], x: float, y: float, staff_top: float) -> None:
        top = staff_top
        bottom = staff_top + STAFF_LINE_SPACING * 4
        line_y = bottom + STAFF_LINE_SPACING
        while line_y <= y + 0.1:
            lines.append(f'  <line x1="{x - 11:g}" y1="{line_y:g}" x2="{x + 11:g}" y2="{line_y:g}" stroke="#1f2933" stroke-width="1"/>')
            line_y += STAFF_LINE_SPACING

        line_y = top - STAFF_LINE_SPACING
        while line_y >= y - 0.1:
            lines.append(f'  <line x1="{x - 11:g}" y1="{line_y:g}" x2="{x + 11:g}" y2="{line_y:g}" stroke="#1f2933" stroke-width="1"/>')
            line_y -= STAFF_LINE_SPACING

    @staticmethod
    def _slot_x(measure_left: float, slot_offset: int) -> float:
        return measure_left + 24 + slot_offset * ((MEASURE_WIDTH - 42) / MEASURE_SLOTS)

    @staticmethod
    def _pitch_y(note: NoteEvent, staff_top: float, is_bass: bool) -> float:
        bottom_reference = SheetSvgExporter._diatonic_index("G", 2) if is_bass else SheetSvgExporter._diatonic_index("E", 4)
        pitch_index = SheetSvgExporter._diatonic_index(note.step, note.octave)
        bottom_line_y = staff_top + STAFF_LINE_SPACING * 4
        return bottom_line_y - (pitch_index - bottom_reference) * (STAFF_LINE_SPACING / 2)

    @staticmethod
    def _diatonic_index(step: str, octave: int) -> int:
        return octave * 7 + STEP_OFFSETS[step.upper()]
