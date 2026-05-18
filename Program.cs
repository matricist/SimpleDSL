/*
Sample input.dsl:

@title: Simple Piano Sketch
@unit: 1/16
@tempo: 120q
@time: 4/4
@key: C
@track: RH
C4-4E4-4G4-4; ; ; ; C5-8;
@track: LH
C3-8; ; G2-8; ;
*/

using SimpleDSL;

var inputPath = args.Length > 0 ? args[0] : "input.dsl";
var outputPath = args.Length > 1 ? args[1] : "output.musicxml";

try
{
    var dsl = File.ReadAllText(inputPath);
    var score = DslParser.Parse(dsl);
    var musicXml = MusicXmlExporter.Export(score);

    File.WriteAllText(outputPath, musicXml);
    Console.WriteLine($"Wrote MusicXML to {outputPath}");
}
catch (Exception ex)
{
    Console.Error.WriteLine($"Error: {ex.Message}");
    Environment.ExitCode = 1;
}
