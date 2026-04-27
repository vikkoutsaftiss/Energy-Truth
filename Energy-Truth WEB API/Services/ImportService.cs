namespace Energy_Truth_WEB_API;

using CsvHelper;
using CsvHelper.Configuration;
using System.Globalization;
using Energy_Truth.Shared;
using Energy_Truth.Shared.Providers ;
using Energy_Truth_WEB_API;

public class ImportService : IImportService
{
    private readonly IEnumerable<IEnergyProvider> _energyProvider;

    public ImportService(IEnumerable<IEnergyProvider> energyProvider)
    {
        _energyProvider = energyProvider;
    }
    public List<EnergyImportDTO> ProcessCsv(Stream fileStream, Dictionary<string, string> mapping, string providerName) // Deze methode verwerkt het CSV-bestand en retourneert een lijst van EnergyImportDTO's
    {
        var provider = _energyProvider.FirstOrDefault(p => p.Name == providerName); // Hier wordt de provider opgezocht op basis van de naam die is meegegeven in de parameters.

        var config = new CsvConfiguration(CultureInfo.InvariantCulture) // Dit regelt de configuratie voor het CSV bestand.
        {
            HasHeaderRecord = true, // Er is een header record aanwezig in het CSV bestand
            Delimiter = provider.Delimiter, //de delimiter wordt opgehaald uit de provider instellingen. Dit is het teken dat gebruikt word om de verschillende velden in het CSV bestand te scheiden.
            Mode = provider.CsvMode, // De CsvMode wordt opgehaald uit de provider instellingen. Dit bepaalt hoe de CSV parser omgaat met bepaalde situaties, zoals ontbrekende velden of extra velden.
            HeaderValidated = null, //  Deze instelling zorgt ervoor dat er geen foutmelding wordt gegeven als er een veld in de header ontbreekt dat niet in de mapping is opgenomen
            MissingFieldFound = null // Deze instelling zorgt ervoor dat er geen foutmelding wordt gegeven als er een veld in de CSV ontbreekt dat niet in de mapping is opgenomen
        };        

        using var reader = new StreamReader(fileStream);
        var rawContent = reader.ReadToEnd();

        if (provider.StripRowQuotes)
            rawContent = rawContent.Replace("\"", "");

        using var stringReader = new StringReader(rawContent);
        using var csv = new CsvReader(stringReader, config);

        csv.Context.RegisterClassMap(new EnergyImportMap(mapping, provider.DateFormat)); //de custom mapping die gemaakt is wordt hier toegepast op de csv data.

        return csv.GetRecords<EnergyImportDTO>().ToList(); // de csv data wordt hier omgezet naar een lijst van EnergyImportDTO's en geretourneerd.
    }


}