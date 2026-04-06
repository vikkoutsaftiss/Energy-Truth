namespace Energy_Truth_WEB_API;

using CsvHelper;
using CsvHelper.Configuration;
using System.Globalization;
using Energy_Truth.Shared;
using Energy_Truth_WEB_API;

public class ImportService
{
    public List<EnergyImportDTO> ProcessCsv(Stream fileStream)
    {
        // Gebruik InvariantCulture omdat je getallen een punt (.) als decimaal hebben
        var config = new CsvConfiguration(CultureInfo.InvariantCulture)
        {
            HasHeaderRecord = true, // We hebben nu koppen!
            Delimiter = ",",        // De komma scheidt de kolommen
            HeaderValidated = null, // Negeer het als een kopje net anders is
            MissingFieldFound = null
        };

        using var reader = new StreamReader(fileStream);
        using var csv = new CsvReader(reader, config);
        return csv.GetRecords<EnergyImportDTO>().ToList();
    }


}