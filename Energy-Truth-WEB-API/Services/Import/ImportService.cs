namespace Energy_Truth_WEB_API.Services.Import;

using CsvHelper;
using CsvHelper.Configuration;
using Energy_Truth.Shared;
using Energy_Truth.Shared.Providers;
using Energy_Truth_WEB_API.Services.Mappers;
using System.Globalization;

public class ImportService : IImportService
{
    private readonly IEnumerable<IEnergyProvider> _energyProvider;

    public ImportService(IEnumerable<IEnergyProvider> energyProvider)
    {
        _energyProvider = energyProvider;
    }

    public async Task<List<EnergyImportDTO>> ProcessCsv(Stream fileStream, Dictionary<string, string> mapping, string providerName)
    {
        using var peekReader = new StreamReader(fileStream, leaveOpen: true);
        var headerLine = await peekReader.ReadLineAsync();
        var firstDataLine = await peekReader.ReadLineAsync();
        fileStream.Position = 0;

        var detectedDelimiter = DetectDelimiter(headerLine ?? string.Empty);

        if (providerName != "Handmatige invoer")
        {
            
            var provider = _energyProvider.FirstOrDefault(p => p.Name == providerName);

            var resolvedDelimiter = detectedDelimiter != '\0'
                ? detectedDelimiter.ToString()
                : provider.Delimiter;

            var detectedDateFormat = DetectDateFormat(headerLine ?? string.Empty, firstDataLine ?? string.Empty, mapping, detectedDelimiter);

            var config = new CsvConfiguration(CultureInfo.InvariantCulture)
            {
                HasHeaderRecord = true,
                Delimiter = resolvedDelimiter,
                Mode = provider.CsvMode,
                HeaderValidated = null,
                MissingFieldFound = null
            };

            using var reader = new StreamReader(fileStream);
            var rawContent = await reader.ReadToEndAsync();

            if (provider.StripRowQuotes)
                rawContent = rawContent.Replace("\"", "");

            using var stringReader = new StringReader(rawContent);
            using var csv = new CsvReader(stringReader, config);

            var cleanedMapping = mapping
                .Where(kvp => !string.IsNullOrEmpty(kvp.Value))
                .ToDictionary(k => k.Key, k => k.Value);

            csv.Context.RegisterClassMap(new EnergyImportMap(cleanedMapping, new List<string> { detectedDateFormat }));

            var results = new List<EnergyImportDTO>();
            while (await csv.ReadAsync())
            {
                try
                {
                    results.Add(csv.GetRecord<EnergyImportDTO>());
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Rij {csv.Context.Parser.Row} geskipt: {ex.InnerException?.Message ?? ex.Message}");
                }
            }
            return results;
        }

        // Handmatige invoer
        var manualDelimiter = detectedDelimiter != '\0' ? detectedDelimiter.ToString() : ",";

        var detectedManualDateFormat = DetectDateFormat(headerLine ?? string.Empty, firstDataLine ?? string.Empty, mapping, detectedDelimiter);

        var manualConfig = new CsvConfiguration(CultureInfo.InvariantCulture)
        {
            HasHeaderRecord = true,
            Delimiter = manualDelimiter,
            Mode = CsvMode.RFC4180,
            HeaderValidated = null,
            MissingFieldFound = null
        };

        using var manualReader = new StreamReader(fileStream);
        var rawManualContent = await manualReader.ReadToEndAsync();
        using var manualStringReader = new StringReader(rawManualContent);
        using var manualCsv = new CsvReader(manualStringReader, manualConfig);

        var cleanedManualMapping = mapping
            .Where(kvp => !string.IsNullOrEmpty(kvp.Value))
            .ToDictionary(k => k.Key, k => k.Value);

        manualCsv.Context.RegisterClassMap(new EnergyImportMap(cleanedManualMapping, new List<string> { detectedManualDateFormat }));

        var manualResults = new List<EnergyImportDTO>();
        while (await manualCsv.ReadAsync())
        {
            try
            {
                manualResults.Add(manualCsv.GetRecord<EnergyImportDTO>());
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Rij {manualCsv.Context.Parser.Row} geskipt: {ex.InnerException?.Message ?? ex.Message}");
            }
        }
        return manualResults;
    }

    private static char DetectDelimiter(string headerLine)
    {
        var delimiters = new[] { ',', ';', '\t' };
        var best = delimiters.MaxBy(d => headerLine.Count(c => c == d));
        return headerLine.Count(c => c == best) > 0 ? best : '\0';
    }

    private static string DetectDateFormat(string headerLine, string firstDataLine, Dictionary<string, string> mapping, char delimiter)
    {
        var standardTimeSettings = "yyyy-MM-dd HH:mm";

        if (!mapping.TryGetValue(nameof(EnergyImportDTO.Time), out var timeCol))
            return standardTimeSettings;

        var headers = headerLine.Split(delimiter);
        var values = firstDataLine.Split(delimiter);

        var index = Array.IndexOf(headers, timeCol);
        if (index < 0 || index >= values.Length)
            return standardTimeSettings;

        var sampleValue = values[index].Trim().Trim('"');

        var formats = new[]
        {
            "yyyy-MM-dd HH:mm",
            "yyyy-MM-dd HH:mm:ss",
            "yyyy-MM-ddTHH:mm",
            "yyyy-MM-ddTHH:mm:ss",
            "yyyy-MM-ddTHH:mm:ssZ",
            "yyyy/MM/dd HH:mm",
            "yyyy/MM/dd HH:mm:ss",
            "dd-MM-yyyy HH:mm",
            "dd-MM-yyyy HH:mm:ss",
            "dd/MM/yyyy HH:mm",
            "dd/MM/yyyy HH:mm:ss",
            "dd.MM.yyyy HH:mm",
            "dd.MM.yyyy HH:mm:ss",
            "MM/dd/yyyy HH:mm",
            "MM/dd/yyyy HH:mm:ss",
            "MM-dd-yyyy HH:mm",
            "MM-dd-yyyy HH:mm:ss",
            "yyyy-MM-dd",
            "dd-MM-yyyy",
            "dd/MM/yyyy",
            "MM/dd/yyyy",
        };

        foreach (var format in formats)
        {
            if (DateTime.TryParseExact(sampleValue, format, CultureInfo.InvariantCulture, DateTimeStyles.None, out _))
                return format;
        }

        return standardTimeSettings;
    }
}