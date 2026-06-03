namespace Energy_Truth_WEB_API.Services.Import;

using CsvHelper;
using CsvHelper.Configuration;
using Energy_Truth.Shared;
using Energy_Truth.Shared.Providers;
using Energy_Truth_WEB_API.Services.Mappers;
using NetTopologySuite.Mathematics;
using System.Globalization;
using static Supabase.Gotrue.Constants;

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
        fileStream.Position = 0;

        var detectedDelimiter = DetectDelimiter(headerLine ?? string.Empty);

        if (providerName != "Handmatige invoer")
        {
            var provider = _energyProvider.FirstOrDefault(p => p.Name == providerName);

            var delimiter = detectedDelimiter != '\0' ? detectedDelimiter.ToString() : provider.Delimiter;

            var config = new CsvConfiguration(CultureInfo.InvariantCulture)
            {
                HasHeaderRecord = true,
                Delimiter = delimiter,
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

            csv.Context.RegisterClassMap(new EnergyImportMap(mapping, provider.DateFormat));
            return csv.GetRecords<EnergyImportDTO>().ToList();
        }

        // Handmatige invoer
        var manualDelimiter = detectedDelimiter != '\0' ? detectedDelimiter.ToString() : ",";

        var manualConfig = new CsvConfiguration(CultureInfo.InvariantCulture)
        {
            HasHeaderRecord = true,
            Delimiter = manualDelimiter,
            Mode = CsvMode.NoEscape,
            HeaderValidated = null,
            MissingFieldFound = null
        };

        var date = new List<string> { "yyyy-MM-dd HH:mm" };

        using var manualReader = new StreamReader(fileStream);
        var rawManualContent = await manualReader.ReadToEndAsync();
        using var manualStringReader = new StringReader(rawManualContent);
        using var manualCsv = new CsvReader(manualStringReader, manualConfig);

        manualCsv.Context.RegisterClassMap(new EnergyImportMap(mapping, date));
        return manualCsv.GetRecords<EnergyImportDTO>().ToList();
    }

    private char DetectDelimiter(string headerLine)
    {
        var delimiters = new[] { ',', ';', '\t' };
        return delimiters.OrderByDescending(d => headerLine.Count(c => c == d)).FirstOrDefault();
    }


}