using Energy_Truth.Shared;
using Energy_Truth_WEB_API;
using Energy_Truth_WEB_API.Services;
using Microsoft.AspNetCore.Mvc;
using System.Text.Json;

[ApiController]
[Route("api/[controller]")] // Dit zorgt dat de URL /api/import wordt
public class ImportController : ControllerBase
{
    private readonly ImportService _importService; // de importService wordt geinjecteerd via de constructor, dit is de service die verantwoordelijk is voor het verwerken van het CSV bestand.
    private readonly EnergyCalculationService _energyCalculationService; // de energyCalculationService wordt geinjecteerd via de constructor, dit is de service die verantwoordelijk is voor het uitvoeren van de energie berekeningen.

    public ImportController(ImportService importService, EnergyCalculationService energyCalculationService)
    {
        _importService = importService; 
        _energyCalculationService = energyCalculationService;
    }

    [HttpPost("csv")] // wanneer de post actie CSV uitgevoerd wordt wordt deze methode aangeroepen. 
    public async Task<IActionResult> UploadCsv([FromForm] IFormFile file, [FromForm] string mapping)
    // een a synchrone methode. Async zorgt ervoor dat de server wacht op de verwerking zonder te blokkeren.
    //IActionResult is het type resultaat dat de API teruggeeft. Dit is flexibel en kan verschillende soorten HTTP-responses bevatten (zoals Ok met data, BadRequest met een string welke aangeeft wat de gebruiker fout gedaan heeft, etc.).
    // [FromForm] zorgt ervoor dat de API in het bestand kijkt voor de data. Normaal wordt dit uit een JSON gehaald.
    // IFormFile is een interface die een bestand vertegenwoordigt dat via een HTTP-request is geüpload. In dit geval verwachten we een CSV-bestand.
    // string mapping is een JSON-string die de kolomnaam in het CSV-bestand koppelt aan de property naam in de EnergyImportDTO. Dit maakt het mogelijk om flexibel te zijn in de structuur van het CSV-bestand dat gebruikers kunnen uploaden.
    {
        if (file == null || file.Length == 0)
            return BadRequest("Geen bestand ontvangen."); //als het bestand niet geupload is dan wordt er een badrequest teruggegeven met een duidelijke melding voor de gebruiker.

        if (string.IsNullOrEmpty(mapping))
            return BadRequest("Mapping informatie ontbreekt."); //als de mapping informatie niet is meegegeven dan wordt er een badrequest teruggegeven met een duidelijke melding voor de gebruiker.

        try
        {
            // 2. Veilig deserialiseren
            var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true }; // hier worden de json deserialize opties aangegeven. Deze optie zorgt ervoor dat de mapping niet gevoelig is voor hoofdletters.
            var columnMapping = JsonSerializer.Deserialize<Dictionary<string, string>>(mapping, options); // de opties van hierboven en de mapping worden hier gecombineerd.

            if (columnMapping == null) // als de variabele die hiervoor aangemaakt wordt leeg is dan wordt er een badrequest teruggegeven.
                return BadRequest("Mapping kon niet worden verwerkt.");

            // 3. Verwerken
            using var stream = file.OpenReadStream(); // het geuploade bestand wordt gelezen.

            // We maken er een Task van mocht je service nog niet async zijn
            var result = await Task.Run(() => _importService.ProcessCsv(stream, columnMapping)); // de importService wordt aangeroepen om de CSV te verwerken. Dit gebeurt in een aparte Task zodat de server niet blokkeert tijdens het verwerken van het bestand.

            return Ok(result); // voltooid? Dan wordt er een Ok teruggegeven met de lijst van EnergyImportDTO's die uit het CSV-bestand zijn gehaald.
        }
        catch (JsonException ex)
        {
            return BadRequest($"Fout in mapping formaat: {ex.Message}"); //als er een fout is in het JSON-formaat van de mapping, wordt er een badrequest teruggegeven met een duidelijke melding voor de gebruiker.
        }
        catch (Exception ex)
        {
            // Log de fout voor jezelf en stuur een duidelijke melding naar de front-end
            return StatusCode(500, $"Interne fout tijdens import: {ex.Message}");
        }
    }

    [HttpPost("calculate")]
    public IActionResult Calculate([FromBody] List<EnergyImportDTO> data) // Dit is de methode die wordt aangeroepen wanneer er op de knop bereken gedrukt wordt. Het geeft een lijst van EnergyImportDTO's mee. Hier wordt frombody gebruikt omdat deze data uit een JSON payload komt in plaats van een bestand.
    {
        if (data == null || !data.Any())  // wanneer het geen data bevat zal het een foutmelding geven.
            return BadRequest("Geen data ontvangen.");

        var result = _energyCalculationService.CalculateEnergy(data); // de energyCalculationService wordt aangeroepen om de berekeningen uit te voeren op de lijst van EnergyImportDTO's. Het resultaat is een CalculationResultDTO die het totaal van import en export in kWh bevat.
        return Ok(result); // het resultaat van de berekeningen wordt teruggegeven als een Ok response.
    }
}
