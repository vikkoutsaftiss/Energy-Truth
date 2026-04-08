namespace Energy_Truth_WEB_API;

using CsvHelper;
using CsvHelper.Configuration;
using System.Globalization;
using Energy_Truth.Shared;
using Energy_Truth_WEB_API;

public class ImportService
{
    public List<EnergyImportDTO> ProcessCsv(Stream fileStream, Dictionary<string, string> mapping) // Deze methode verwerkt het CSV-bestand en retourneert een lijst van EnergyImportDTO's
    {
        var config = new CsvConfiguration(CultureInfo.InvariantCulture) // Dit regelt de configuratie voor het CSV bestand.
        {
            HasHeaderRecord = true, // Er is een header record aanwezig in het CSV bestand
            Delimiter = ",", // De delimiter die gebruikt wordt in het CSV bestand is een komma
            HeaderValidated = null, //  Deze instelling zorgt ervoor dat er geen foutmelding wordt gegeven als er een veld in de header ontbreekt dat niet in de mapping is opgenomen
            MissingFieldFound = null // Deze instelling zorgt ervoor dat er geen foutmelding wordt gegeven als er een veld in de CSV ontbreekt dat niet in de mapping is opgenomen
        };

        using var reader = new StreamReader(fileStream); //de inhoud van de CSV wordt hier toegekend aan de var reader.
        using var csv = new CsvReader(reader, config); // de instellingen die hierboven genoteerd staan wordt hier gecombineerd met de inhoud van de CSV. De inhoud wordt gecheckt.

        csv.Context.RegisterClassMap(new EnergyImportMap(mapping)); //de custom mapping die gemaakt is wordt hier toegepast op de csv data.

        return csv.GetRecords<EnergyImportDTO>().ToList(); // de csv data wordt hier omgezet naar een lijst van EnergyImportDTO's en geretourneerd.
    }


}