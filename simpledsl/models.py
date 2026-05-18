from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction


@dataclass
class ScoreMetadata:
    title: str = "Untitled"
    unit: str = "1/16"
    tempo_quarter_notes_per_minute: int = 120
    beats: int = 4
    beat_type: int = 4
    key: str = "C"


@dataclass(frozen=True)
class TupletInfo:
    actual_notes: int
    normal_notes: int
    index: int
    count: int
    normal_duration_slots: Fraction
    group_start_slot: Fraction


@dataclass(frozen=True)
class ChordSymbol:
    symbol: str
    root_step: str
    root_alter: int
    kind: str
    kind_text: str
    start_slot: Fraction
    track_name: str
    bass_step: str | None = None
    bass_alter: int = 0


@dataclass
class NoteEvent:
    step: str
    alter: int
    octave: int
    start_slot: Fraction
    duration_slots: Fraction
    track_name: str
    ornament: str | None = None
    tuplet: TupletInfo | None = None

    @property
    def end_slot(self) -> Fraction:
        return self.start_slot + self.duration_slots


@dataclass
class Track:
    name: str
    cursor_slot: int = 0
    notes: list[NoteEvent] = field(default_factory=list)
    chord_symbols: list[ChordSymbol] = field(default_factory=list)

    @property
    def end_slot(self) -> Fraction:
        positions = [Fraction(self.cursor_slot)]
        positions.extend(note.end_slot for note in self.notes)
        positions.extend(chord.start_slot for chord in self.chord_symbols)
        return max(positions)


@dataclass
class Score:
    metadata: ScoreMetadata = field(default_factory=ScoreMetadata)
    tracks: dict[str, Track] = field(default_factory=dict)

    def get_or_create_track(self, track_name: str) -> Track:
        normalized = track_name.upper()
        if normalized not in self.tracks:
            self.tracks[normalized] = Track(normalized)
        return self.tracks[normalized]
