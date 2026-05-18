namespace SimpleDSL;

public sealed class ScoreMetadata
{
    public string Title { get; set; } = "Untitled";
    public string Unit { get; set; } = "1/16";
    public int TempoQuarterNotesPerMinute { get; set; } = 120;
    public int Beats { get; set; } = 4;
    public int BeatType { get; set; } = 4;
    public string Key { get; set; } = "C";
}

public sealed class Score
{
    public ScoreMetadata Metadata { get; } = new();
    public Dictionary<string, Track> Tracks { get; } = new(StringComparer.OrdinalIgnoreCase);

    public Track GetOrCreateTrack(string trackName)
    {
        if (!Tracks.TryGetValue(trackName, out var track))
        {
            track = new Track(trackName);
            Tracks[trackName] = track;
        }

        return track;
    }
}

public sealed class Track
{
    public Track(string name)
    {
        Name = name;
    }

    public string Name { get; }
    public int CursorSlot { get; set; }
    public List<NoteEvent> Notes { get; } = new();

    public int EndSlot => Notes.Count == 0
        ? CursorSlot
        : Math.Max(CursorSlot, Notes.Max(n => n.StartSlot + n.DurationSlots));
}

public sealed class NoteEvent
{
    public char Step { get; set; }
    public int Alter { get; set; }
    public int Octave { get; set; }
    public int StartSlot { get; set; }
    public int DurationSlots { get; set; }
    public string TrackName { get; set; } = "";
}
