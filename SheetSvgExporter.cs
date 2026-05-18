using System.Globalization;
using System.Security;
using System.Text;

namespace SimpleDSL;

public static class SheetSvgExporter
{
    private const int MeasureSlots = 16;
    private const int MeasuresPerSystem = 4;
    private const double PageWidth = 1180;
    private const double MarginLeft = 72;
    private const double MarginTop = 72;
    private const double MeasureWidth = 250;
    private const double StaffLineSpacing = 10;
    private const double StaffGap = 86;
    private const double SystemGap = 190;

    private static readonly IReadOnlyDictionary<char, int> StepOffsets = new Dictionary<char, int>
    {
        ['C'] = 0,
        ['D'] = 1,
        ['E'] = 2,
        ['F'] = 3,
        ['G'] = 4,
        ['A'] = 5,
        ['B'] = 6
    };

    public static string Export(Score score)
    {
        var measureCount = Math.Max(1, score.Tracks.Values.Select(t => t.EndSlot).DefaultIfEmpty(0).Max() + MeasureSlots - 1) / MeasureSlots;
        measureCount = Math.Max(1, measureCount);

        var systemCount = (measureCount + MeasuresPerSystem - 1) / MeasuresPerSystem;
        var pageHeight = MarginTop + 70 + systemCount * SystemGap + 40;
        var title = SecurityElement.Escape(score.Metadata.Title) ?? "";

        var sb = new StringBuilder();
        sb.AppendLine("<?xml version=\"1.0\" encoding=\"UTF-8\"?>");
        sb.AppendLine($"<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{Format(PageWidth)}\" height=\"{Format(pageHeight)}\" viewBox=\"0 0 {Format(PageWidth)} {Format(pageHeight)}\">");
        sb.AppendLine("  <rect width=\"100%\" height=\"100%\" fill=\"#fffdf8\"/>");
        sb.AppendLine($"  <text x=\"{Format(PageWidth / 2)}\" y=\"42\" text-anchor=\"middle\" font-family=\"Georgia, serif\" font-size=\"26\" fill=\"#1f2933\">{title}</text>");
        sb.AppendLine($"  <text x=\"{Format(PageWidth / 2)}\" y=\"66\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"13\" fill=\"#52606d\">{SecurityElement.Escape(score.Metadata.Key)} major · {score.Metadata.Beats}/{score.Metadata.BeatType} · {score.Metadata.TempoQuarterNotesPerMinute} BPM</text>");

        for (var systemIndex = 0; systemIndex < systemCount; systemIndex++)
        {
            var firstMeasure = systemIndex * MeasuresPerSystem;
            var measuresInSystem = Math.Min(MeasuresPerSystem, measureCount - firstMeasure);
            var systemY = MarginTop + 50 + systemIndex * SystemGap;

            DrawSystem(sb, score, firstMeasure, measuresInSystem, systemY);
        }

        sb.AppendLine("</svg>");
        return sb.ToString();
    }

    private static void DrawSystem(StringBuilder sb, Score score, int firstMeasure, int measuresInSystem, double systemY)
    {
        var trebleTop = systemY;
        var bassTop = systemY + StaffGap;
        var left = MarginLeft;
        var right = MarginLeft + measuresInSystem * MeasureWidth;

        DrawStaff(sb, left, right, trebleTop);
        DrawStaff(sb, left, right, bassTop);
        DrawBrace(sb, left - 24, trebleTop, bassTop + StaffLineSpacing * 4);

        sb.AppendLine($"  <text x=\"{Format(left - 44)}\" y=\"{Format(trebleTop + 25)}\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"12\" fill=\"#52606d\">RH</text>");
        sb.AppendLine($"  <text x=\"{Format(left - 44)}\" y=\"{Format(bassTop + 25)}\" text-anchor=\"middle\" font-family=\"Arial, sans-serif\" font-size=\"12\" fill=\"#52606d\">LH</text>");
        sb.AppendLine($"  <text x=\"{Format(left - 12)}\" y=\"{Format(trebleTop + 31)}\" text-anchor=\"middle\" font-family=\"Georgia, serif\" font-size=\"36\" fill=\"#1f2933\">𝄞</text>");
        sb.AppendLine($"  <text x=\"{Format(left - 12)}\" y=\"{Format(bassTop + 32)}\" text-anchor=\"middle\" font-family=\"Georgia, serif\" font-size=\"34\" fill=\"#1f2933\">𝄢</text>");

        for (var i = 0; i <= measuresInSystem; i++)
        {
            var x = left + i * MeasureWidth;
            sb.AppendLine($"  <line x1=\"{Format(x)}\" y1=\"{Format(trebleTop)}\" x2=\"{Format(x)}\" y2=\"{Format(trebleTop + StaffLineSpacing * 4)}\" stroke=\"#1f2933\" stroke-width=\"1\"/>");
            sb.AppendLine($"  <line x1=\"{Format(x)}\" y1=\"{Format(bassTop)}\" x2=\"{Format(x)}\" y2=\"{Format(bassTop + StaffLineSpacing * 4)}\" stroke=\"#1f2933\" stroke-width=\"1\"/>");

            if (i < measuresInSystem)
            {
                sb.AppendLine($"  <text x=\"{Format(x + 8)}\" y=\"{Format(trebleTop - 10)}\" font-family=\"Arial, sans-serif\" font-size=\"11\" fill=\"#6b7280\">{firstMeasure + i + 1}</text>");
            }
        }

        DrawTrack(sb, score.GetOrCreateTrack("RH"), firstMeasure, measuresInSystem, trebleTop, isBass: false);
        DrawTrack(sb, score.GetOrCreateTrack("LH"), firstMeasure, measuresInSystem, bassTop, isBass: true);
    }

    private static void DrawStaff(StringBuilder sb, double left, double right, double top)
    {
        for (var line = 0; line < 5; line++)
        {
            var y = top + line * StaffLineSpacing;
            sb.AppendLine($"  <line x1=\"{Format(left)}\" y1=\"{Format(y)}\" x2=\"{Format(right)}\" y2=\"{Format(y)}\" stroke=\"#1f2933\" stroke-width=\"1\"/>");
        }
    }

    private static void DrawBrace(StringBuilder sb, double x, double top, double bottom)
    {
        var middle = (top + bottom) / 2;
        sb.AppendLine($"  <path d=\"M {Format(x + 14)} {Format(top)} C {Format(x - 10)} {Format(top + 24)}, {Format(x - 10)} {Format(middle - 20)}, {Format(x + 10)} {Format(middle)} C {Format(x - 10)} {Format(middle + 20)}, {Format(x - 10)} {Format(bottom - 24)}, {Format(x + 14)} {Format(bottom)}\" fill=\"none\" stroke=\"#1f2933\" stroke-width=\"2\"/>");
    }

    private static void DrawTrack(StringBuilder sb, Track track, int firstMeasure, int measuresInSystem, double staffTop, bool isBass)
    {
        for (var measureOffset = 0; measureOffset < measuresInSystem; measureOffset++)
        {
            var measureNumber = firstMeasure + measureOffset;
            var measureStart = measureNumber * MeasureSlots;
            var measureEnd = measureStart + MeasureSlots;
            var measureLeft = MarginLeft + measureOffset * MeasureWidth;

            var segments = track.Notes
                .Where(n => n.StartSlot < measureEnd && n.StartSlot + n.DurationSlots > measureStart)
                .Select(n => new DrawSegment(n, Math.Max(n.StartSlot, measureStart), Math.Min(n.StartSlot + n.DurationSlots, measureEnd)))
                .GroupBy(s => s.StartSlot)
                .OrderBy(g => g.Key)
                .ToList();

            var cursor = measureStart;
            foreach (var group in segments)
            {
                if (group.Key > cursor)
                {
                    DrawRest(sb, measureLeft, staffTop, group.Key - measureStart, group.Key - cursor);
                }

                var ordered = group
                    .OrderBy(s => GetPitchY(s.Note, staffTop, isBass))
                    .ToList();

                for (var i = 0; i < ordered.Count; i++)
                {
                    DrawNote(sb, measureLeft, staffTop, ordered[i], isBass, i);
                }

                cursor = Math.Max(cursor, group.Max(s => s.EndSlot));
            }

            if (cursor < measureEnd)
            {
                DrawRest(sb, measureLeft, staffTop, cursor - measureStart, measureEnd - cursor);
            }
        }
    }

    private static void DrawNote(StringBuilder sb, double measureLeft, double staffTop, DrawSegment segment, bool isBass, int chordIndex)
    {
        var x = SlotToX(measureLeft, segment.StartSlot % MeasureSlots) + chordIndex * 4;
        var y = GetPitchY(segment.Note, staffTop, isBass);
        var stemUp = y >= staffTop + StaffLineSpacing * 2;
        var stemX = stemUp ? x + 6 : x - 6;
        var stemEndY = stemUp ? y - 34 : y + 34;
        var fill = segment.DurationSlots <= 8 ? "#1f2933" : "#fffdf8";

        DrawLedgerLines(sb, x, y, staffTop);
        sb.AppendLine($"  <ellipse cx=\"{Format(x)}\" cy=\"{Format(y)}\" rx=\"7\" ry=\"5\" transform=\"rotate(-18 {Format(x)} {Format(y)})\" fill=\"{fill}\" stroke=\"#1f2933\" stroke-width=\"1.5\"/>");
        sb.AppendLine($"  <line x1=\"{Format(stemX)}\" y1=\"{Format(y)}\" x2=\"{Format(stemX)}\" y2=\"{Format(stemEndY)}\" stroke=\"#1f2933\" stroke-width=\"1.5\"/>");

        if (segment.StartSlot > segment.Note.StartSlot)
        {
            sb.AppendLine($"  <path d=\"M {Format(x - 18)} {Format(y + 14)} Q {Format(x)} {Format(y + 24)} {Format(x + 18)} {Format(y + 14)}\" fill=\"none\" stroke=\"#1f2933\" stroke-width=\"1\"/>");
        }

        if (segment.EndSlot < segment.Note.StartSlot + segment.Note.DurationSlots)
        {
            sb.AppendLine($"  <path d=\"M {Format(x + 10)} {Format(y + 14)} Q {Format(x + 29)} {Format(y + 24)} {Format(x + 48)} {Format(y + 14)}\" fill=\"none\" stroke=\"#1f2933\" stroke-width=\"1\"/>");
        }
    }

    private static void DrawRest(StringBuilder sb, double measureLeft, double staffTop, int startOffset, int duration)
    {
        if (duration <= 0)
        {
            return;
        }

        var x = SlotToX(measureLeft, startOffset);
        var y = staffTop + StaffLineSpacing * 2;
        sb.AppendLine($"  <text x=\"{Format(x)}\" y=\"{Format(y + 7)}\" text-anchor=\"middle\" font-family=\"Georgia, serif\" font-size=\"20\" fill=\"#52606d\">𝄽</text>");
    }

    private static void DrawLedgerLines(StringBuilder sb, double x, double y, double staffTop)
    {
        var top = staffTop;
        var bottom = staffTop + StaffLineSpacing * 4;

        for (var lineY = bottom + StaffLineSpacing; lineY <= y + 0.1; lineY += StaffLineSpacing)
        {
            sb.AppendLine($"  <line x1=\"{Format(x - 11)}\" y1=\"{Format(lineY)}\" x2=\"{Format(x + 11)}\" y2=\"{Format(lineY)}\" stroke=\"#1f2933\" stroke-width=\"1\"/>");
        }

        for (var lineY = top - StaffLineSpacing; lineY >= y - 0.1; lineY -= StaffLineSpacing)
        {
            sb.AppendLine($"  <line x1=\"{Format(x - 11)}\" y1=\"{Format(lineY)}\" x2=\"{Format(x + 11)}\" y2=\"{Format(lineY)}\" stroke=\"#1f2933\" stroke-width=\"1\"/>");
        }
    }

    private static double SlotToX(double measureLeft, int slotOffset)
    {
        return measureLeft + 24 + slotOffset * ((MeasureWidth - 42) / MeasureSlots);
    }

    private static double GetPitchY(NoteEvent note, double staffTop, bool isBass)
    {
        var bottomReference = isBass
            ? GetDiatonicIndex('G', 2)
            : GetDiatonicIndex('E', 4);
        var pitchIndex = GetDiatonicIndex(note.Step, note.Octave);
        var bottomLineY = staffTop + StaffLineSpacing * 4;

        return bottomLineY - (pitchIndex - bottomReference) * (StaffLineSpacing / 2);
    }

    private static int GetDiatonicIndex(char step, int octave)
    {
        return octave * 7 + StepOffsets[char.ToUpperInvariant(step)];
    }

    private static string Format(double value)
    {
        return value.ToString("0.###", CultureInfo.InvariantCulture);
    }

    private sealed record DrawSegment(NoteEvent Note, int StartSlot, int EndSlot)
    {
        public int DurationSlots => EndSlot - StartSlot;
    }
}
