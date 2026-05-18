using System.Security;
using System.Text;

namespace SimpleDSL;

public static class MusicXmlExporter
{
    private const int Divisions = 4;
    private const int MeasureSlots = 16;

    private static readonly IReadOnlyDictionary<string, string> PartIds = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase)
    {
        ["RH"] = "P1",
        ["LH"] = "P2"
    };

    public static string Export(Score score)
    {
        var sb = new StringBuilder();
        var title = SecurityElement.Escape(score.Metadata.Title) ?? "";

        sb.AppendLine("<?xml version=\"1.0\" encoding=\"UTF-8\"?>");
        sb.AppendLine("<!DOCTYPE score-partwise PUBLIC \"-//Recordare//DTD MusicXML 4.0 Partwise//EN\" \"http://www.musicxml.org/dtds/partwise.dtd\">");
        sb.AppendLine("<score-partwise version=\"4.0\">");
        sb.AppendLine($"  <work><work-title>{title}</work-title></work>");
        sb.AppendLine("  <part-list>");
        sb.AppendLine("    <score-part id=\"P1\"><part-name>Right Hand</part-name></score-part>");
        sb.AppendLine("    <score-part id=\"P2\"><part-name>Left Hand</part-name></score-part>");
        sb.AppendLine("  </part-list>");

        AppendPart(sb, score, "RH");
        AppendPart(sb, score, "LH");

        sb.AppendLine("</score-partwise>");
        return sb.ToString();
    }

    private static void AppendPart(StringBuilder sb, Score score, string trackName)
    {
        var track = score.GetOrCreateTrack(trackName);
        var partId = PartIds[trackName];
        var measureCount = Math.Max(1, (track.EndSlot + MeasureSlots - 1) / MeasureSlots);

        sb.AppendLine($"  <part id=\"{partId}\">");
        for (var measureNumber = 1; measureNumber <= measureCount; measureNumber++)
        {
            var measureStart = (measureNumber - 1) * MeasureSlots;
            var measureEnd = measureStart + MeasureSlots;

            sb.AppendLine($"    <measure number=\"{measureNumber}\">");
            if (measureNumber == 1)
            {
                AppendAttributes(sb, score.Metadata, trackName);
                AppendTempo(sb, score.Metadata);
            }

            AppendMeasureContents(sb, track, measureStart, measureEnd);
            sb.AppendLine("    </measure>");
        }

        sb.AppendLine("  </part>");
    }

    private static void AppendAttributes(StringBuilder sb, ScoreMetadata metadata, string trackName)
    {
        sb.AppendLine("      <attributes>");
        sb.AppendLine($"        <divisions>{Divisions}</divisions>");
        sb.AppendLine("        <key>");
        sb.AppendLine($"          <fifths>{KeyToFifths(metadata.Key)}</fifths>");
        sb.AppendLine("        </key>");
        sb.AppendLine("        <time>");
        sb.AppendLine($"          <beats>{metadata.Beats}</beats>");
        sb.AppendLine($"          <beat-type>{metadata.BeatType}</beat-type>");
        sb.AppendLine("        </time>");
        if (trackName.Equals("LH", StringComparison.OrdinalIgnoreCase))
        {
            sb.AppendLine("        <clef>");
            sb.AppendLine("          <sign>F</sign>");
            sb.AppendLine("          <line>4</line>");
            sb.AppendLine("        </clef>");
        }
        else
        {
            sb.AppendLine("        <clef>");
            sb.AppendLine("          <sign>G</sign>");
            sb.AppendLine("          <line>2</line>");
            sb.AppendLine("        </clef>");
        }
        sb.AppendLine("      </attributes>");
    }

    private static void AppendTempo(StringBuilder sb, ScoreMetadata metadata)
    {
        sb.AppendLine($"      <direction placement=\"above\"><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>{metadata.TempoQuarterNotesPerMinute}</per-minute></metronome></direction-type><sound tempo=\"{metadata.TempoQuarterNotesPerMinute}\"/></direction>");
    }

    private static void AppendMeasureContents(StringBuilder sb, Track track, int measureStart, int measureEnd)
    {
        var segments = track.Notes
            .Where(n => n.StartSlot < measureEnd && n.StartSlot + n.DurationSlots > measureStart)
            .Select(n => new NoteSegment(n, Math.Max(n.StartSlot, measureStart)))
            .GroupBy(s => s.StartSlot)
            .OrderBy(g => g.Key)
            .ToList();

        var cursor = measureStart;
        foreach (var group in segments)
        {
            if (group.Key > cursor)
            {
                AppendRestRange(sb, cursor, group.Key);
            }

            var orderedSegments = group
                .OrderByDescending(s => s.Note.DurationSlots)
                .ThenBy(s => s.Note.Step)
                .ThenBy(s => s.Note.Octave)
                .ToList();

            for (var i = 0; i < orderedSegments.Count; i++)
            {
                AppendNoteSegment(sb, orderedSegments[i].Note, orderedSegments[i].StartSlot, measureEnd, i > 0);
            }

            cursor = Math.Max(cursor, group.Max(s => Math.Min(s.Note.StartSlot + s.Note.DurationSlots, measureEnd)));
        }

        if (cursor < measureEnd)
        {
            AppendRestRange(sb, cursor, measureEnd);
        }
    }

    private static void AppendNoteSegment(StringBuilder sb, NoteEvent note, int startSlot, int measureEnd, bool chord)
    {
        var segmentEnd = Math.Min(note.StartSlot + note.DurationSlots, measureEnd);
        var duration = segmentEnd - startSlot;
        if (duration <= 0)
        {
            return;
        }

        var hasPreviousSegment = startSlot > note.StartSlot;
        var hasFollowingSegment = segmentEnd < note.StartSlot + note.DurationSlots;
        AppendPitchedNote(sb, note, duration, chord, hasPreviousSegment, hasFollowingSegment);
    }

    private sealed record NoteSegment(NoteEvent Note, int StartSlot);

    private static void AppendRestRange(StringBuilder sb, int startSlot, int endSlot)
    {
        var remaining = endSlot - startSlot;
        while (remaining > 0)
        {
            AppendRest(sb, remaining);
            remaining = 0;
        }
    }

    private static void AppendPitchedNote(StringBuilder sb, NoteEvent note, int duration, bool chord, bool tieStop, bool tieStart)
    {
        sb.AppendLine("      <note>");
        if (chord)
        {
            sb.AppendLine("        <chord/>");
        }

        sb.AppendLine("        <pitch>");
        sb.AppendLine($"          <step>{note.Step}</step>");
        if (note.Alter != 0)
        {
            sb.AppendLine($"          <alter>{note.Alter}</alter>");
        }

        sb.AppendLine($"          <octave>{note.Octave}</octave>");
        sb.AppendLine("        </pitch>");
        sb.AppendLine($"        <duration>{duration}</duration>");
        if (tieStop)
        {
            sb.AppendLine("        <tie type=\"stop\"/>");
        }

        if (tieStart)
        {
            sb.AppendLine("        <tie type=\"start\"/>");
        }

        sb.AppendLine("        <type>16th</type>");
        if (tieStop || tieStart)
        {
            sb.AppendLine("        <notations>");
            if (tieStop)
            {
                sb.AppendLine("          <tied type=\"stop\"/>");
            }

            if (tieStart)
            {
                sb.AppendLine("          <tied type=\"start\"/>");
            }

            sb.AppendLine("        </notations>");
        }

        sb.AppendLine("      </note>");
    }

    private static void AppendRest(StringBuilder sb, int duration)
    {
        sb.AppendLine("      <note>");
        sb.AppendLine("        <rest/>");
        sb.AppendLine($"        <duration>{duration}</duration>");
        sb.AppendLine("        <type>16th</type>");
        sb.AppendLine("      </note>");
    }

    private static int KeyToFifths(string key)
    {
        return key.Trim() switch
        {
            "Cb" => -7,
            "Gb" => -6,
            "Db" => -5,
            "Ab" => -4,
            "Eb" => -3,
            "Bb" => -2,
            "F" => -1,
            "C" => 0,
            "G" => 1,
            "D" => 2,
            "A" => 3,
            "E" => 4,
            "B" => 5,
            "F#" => 6,
            "C#" => 7,
            _ => 0
        };
    }
}
