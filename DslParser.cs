using System.Text.RegularExpressions;

namespace SimpleDSL;

public static partial class DslParser
{
    private static readonly Regex NoteRegex = new(
        @"(?<step>[A-Ga-g])(?<accidental>#|b)?(?<octave>-?\d+)-(?<duration>\d+)",
        RegexOptions.Compiled);

    public static Score Parse(string dsl)
    {
        var score = new Score();
        Track? currentTrack = null;

        var lines = dsl.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');
        for (var lineIndex = 0; lineIndex < lines.Length; lineIndex++)
        {
            var rawLine = StripInlineComment(lines[lineIndex]).Trim();
            if (rawLine.Length == 0)
            {
                continue;
            }

            if (rawLine.StartsWith('@'))
            {
                currentTrack = ParseMetadataLine(score, rawLine, lineIndex + 1, currentTrack);
                continue;
            }

            if (currentTrack is null)
            {
                throw new FormatException($"Line {lineIndex + 1}: notes must appear after an @track metadata line.");
            }

            ParseMusicLine(rawLine, currentTrack, lineIndex + 1);
        }

        EnsureSupportedMetadata(score.Metadata);
        score.GetOrCreateTrack("RH");
        score.GetOrCreateTrack("LH");

        return score;
    }

    private static Track? ParseMetadataLine(Score score, string line, int lineNumber, Track? currentTrack)
    {
        var colonIndex = line.IndexOf(':');
        if (colonIndex < 0)
        {
            throw new FormatException($"Line {lineNumber}: metadata must be written as @name: value.");
        }

        var name = line[1..colonIndex].Trim().ToLowerInvariant();
        var value = line[(colonIndex + 1)..].Trim();

        switch (name)
        {
            case "title":
                score.Metadata.Title = value;
                return currentTrack;
            case "unit":
                score.Metadata.Unit = value;
                return currentTrack;
            case "tempo":
                score.Metadata.TempoQuarterNotesPerMinute = ParseTempo(value, lineNumber);
                return currentTrack;
            case "time":
                ParseTime(value, score.Metadata, lineNumber);
                return currentTrack;
            case "key":
                score.Metadata.Key = value;
                return currentTrack;
            case "track":
                if (!value.Equals("RH", StringComparison.OrdinalIgnoreCase) &&
                    !value.Equals("LH", StringComparison.OrdinalIgnoreCase))
                {
                    throw new FormatException($"Line {lineNumber}: supported tracks are RH and LH.");
                }

                return score.GetOrCreateTrack(value.ToUpperInvariant());
            default:
                throw new FormatException($"Line {lineNumber}: unsupported metadata '@{name}'.");
        }
    }

    private static void ParseMusicLine(string line, Track track, int lineNumber)
    {
        var segments = line.Split(';');

        for (var i = 0; i < segments.Length; i++)
        {
            var segment = segments[i].Trim();
            if (segment.Length > 0)
            {
                ParseSlotNotes(segment, track, lineNumber);
            }

            if (i < segments.Length - 1)
            {
                track.CursorSlot++;
            }
        }
    }

    private static void ParseSlotNotes(string segment, Track track, int lineNumber)
    {
        var index = 0;
        while (index < segment.Length)
        {
            if (char.IsWhiteSpace(segment[index]))
            {
                index++;
                continue;
            }

            var match = NoteRegex.Match(segment, index);
            if (!match.Success || match.Index != index)
            {
                throw new FormatException($"Line {lineNumber}: invalid note syntax near '{segment[index..]}'.");
            }

            var step = char.ToUpperInvariant(match.Groups["step"].Value[0]);
            var accidental = match.Groups["accidental"].Value;
            var alter = accidental == "#" ? 1 : accidental == "b" ? -1 : 0;
            var octave = int.Parse(match.Groups["octave"].Value);
            var duration = int.Parse(match.Groups["duration"].Value);
            if (duration <= 0)
            {
                throw new FormatException($"Line {lineNumber}: note duration must be greater than zero.");
            }

            track.Notes.Add(new NoteEvent
            {
                Step = step,
                Alter = alter,
                Octave = octave,
                StartSlot = track.CursorSlot,
                DurationSlots = duration,
                TrackName = track.Name
            });

            index += match.Length;
        }
    }

    private static int ParseTempo(string value, int lineNumber)
    {
        if (!value.EndsWith('q') || !int.TryParse(value[..^1], out var tempo) || tempo <= 0)
        {
            throw new FormatException($"Line {lineNumber}: tempo must look like 120q.");
        }

        return tempo;
    }

    private static void ParseTime(string value, ScoreMetadata metadata, int lineNumber)
    {
        var parts = value.Split('/');
        if (parts.Length != 2 ||
            !int.TryParse(parts[0], out var beats) ||
            !int.TryParse(parts[1], out var beatType) ||
            beats <= 0 ||
            beatType <= 0)
        {
            throw new FormatException($"Line {lineNumber}: time signature must look like 4/4.");
        }

        metadata.Beats = beats;
        metadata.BeatType = beatType;
    }

    private static void EnsureSupportedMetadata(ScoreMetadata metadata)
    {
        if (metadata.Unit != "1/16")
        {
            throw new NotSupportedException("Only @unit: 1/16 is supported.");
        }

        if (metadata.Beats != 4 || metadata.BeatType != 4)
        {
            throw new NotSupportedException("Only @time: 4/4 is currently supported.");
        }
    }

    private static string StripInlineComment(string line)
    {
        var commentIndex = line.IndexOf("//", StringComparison.Ordinal);
        return commentIndex >= 0 ? line[..commentIndex] : line;
    }
}
