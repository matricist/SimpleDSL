from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ScoreMetadata:
    title: str = "Untitled"
    unit: str = "1/16"
    tempo_quarter_notes_per_minute: int = 120
    beats: int = 4
    beat_type: int = 4
    key: str = "C"


@dataclass
class NoteEvent:
    step: str
    alter: int
    octave: int
    start_slot: int
    duration_slots: int
    track_name: str

    @property
    def end_slot(self) -> int:
        return self.start_slot + self.duration_slots


@dataclass
class Track:
    name: str
    cursor_slot: int = 0
    notes: list[NoteEvent] = field(default_factory=list)

    @property
    def end_slot(self) -> int:
        if not self.notes:
            return self.cursor_slot
        return max(self.cursor_slot, max(note.end_slot for note in self.notes))


@dataclass
class Score:
    metadata: ScoreMetadata = field(default_factory=ScoreMetadata)
    tracks: dict[str, Track] = field(default_factory=dict)

    def get_or_create_track(self, track_name: str) -> Track:
        normalized = track_name.upper()
        if normalized not in self.tracks:
            self.tracks[normalized] = Track(normalized)
        return self.tracks[normalized]
