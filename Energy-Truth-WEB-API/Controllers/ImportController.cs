using CsvHelper.TypeConversion;
using Energy_Truth.Shared;
using Energy_Truth_WEB_API.Services;
using Energy_Truth_WEB_API.Calculators;
using Microsoft.AspNetCore.Mvc;
using System.Text.Json;
using Energy_Truth.Shared.Repositories;
using Energy_Truth_WEB_API.Services.Import;
using Energy_Truth_WEB_API.Services.DateFilter;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Controllers;


[ApiController]
[Route("api/[controller]")] // Dit zorgt dat de URL /api/import wordt
public class ImportController : ControllerBase
{
    private readonly IImportService _importService; // dit is de service die verantwoordelijk is voor het verwerken van het CSV bestand.
    private readonly IEnergyCalculationService _energyCalculationService; // dit is de service die verantwoordelijk is voor het uitvoeren van de energie berekeningen.
    private readonly IDateFilterService _dateFilterService;
    private readonly IImportCalculator _importCalculator;
    private readonly IUsageDataRepository _usageDataRepository;

    public ImportController(IImportService importService, IEnergyCalculationService energyCalculationService, IDateFilterService dateFilterService, IImportCalculator importCalculator, IUsageDataRepository usageDataRepository)
    {
        _importService = importService; 
        _energyCalculationService = energyCalculationService;
        _dateFilterService = dateFilterService;
        _importCalculator = importCalculator;
        _usageDataRepository = usageDataRepository;
    }

    [HttpPost("csv")] // wanneer de post actie CSV uitgevoerd wordt wordt deze methode aangeroepen. 
    public async Task<IActionResult> UploadCsv([FromForm] IFormFile file, [FromForm] string mapping, [FromForm] string provider, [FromForm] int buildingId)
    // [FromForm] zorgt ervoor dat de API in het bestand kijkt voor de data. Normaal wordt dit uit een JSON gehaald.
    // IFormFile is een interface die een bestand vertegenwoordigt dat via een HTTP-request is geüpload. In dit geval verwachten we een CSV-bestand.
    // string mapping is een JSON-string die de kolomnaam in het CSV-bestand koppelt aan de property naam in de EnergyImportDTO. Dit maakt het mogelijk om flexibel te zijn in de structuur van het CSV-bestand dat gebruikers kunnen uploaden.
    {
        if (file == null || file.Length == 0)
            return BadRequest("Geen bestand ontvangen.");

        if (string.IsNullOrEmpty(mapping))
            return BadRequest("Mapping informatie ontbreekt."); 

        if (!file.FileName.EndsWith(".csv", StringComparison.OrdinalIgnoreCase))
            return BadRequest("Alleen CSV-bestanden zijn toegestaan."); 

        if (file.Length > 10 * 1024 * 1024) // hier wordt er een limiet van 10MB ingesteld voor het bestand dat geupload mag worden. Dit is om te voorkomen dat er te grote bestanden geupload worden die de server kunnen overbelasten.
            return BadRequest("Bestand is te groot. Maximaal toegestaan is 10MB.");    

        try
        {
            var options = new JsonSerializerOptions { PropertyNameCaseInsensitive = true };
            var columnMapping = JsonSerializer.Deserialize<Dictionary<string, string>>(mapping, options);

            if (columnMapping == null)
            {
                return BadRequest("Ongeldige mapping informatie.");
            }
                
            using var stream = file.OpenReadStream();

            var result = await Task.Run(() => _importService.ProcessCsv(stream, columnMapping, provider)); // de importService wordt aangeroepen om de CSV te verwerken. Dit gebeurt in een aparte Task zodat de server niet blokkeert tijdens het verwerken van het bestand.

            return Ok(result);
        }
        catch (TypeConverterException ex)
        {
            return BadRequest($"Datafout in de CSV: {ex.Message}");
        }
        catch (JsonException ex)
        {
            return BadRequest($"Fout in mapping formaat: {ex.Message}"); //als er een fout is in het JSON-formaat van de mapping, wordt er een badrequest teruggegeven met een duidelijke melding voor de gebruiker.
        }
        catch (Exception ex)
        {
            return StatusCode(500, $"Interne fout tijdens import: {ex.Message}");
        }
    }

    [HttpPost("calculate/{provider}")]
    public IActionResult Calculate([FromBody] List<EnergyImportDTO> data, string provider)
    {
        if (data == null || !data.Any() || !ModelState.IsValid)
        {
            return BadRequest("Geen of ongeldige data ontvangen.");
        }

        if (data.Count < 2)
        {
            return BadRequest("Minimaal 2 datapunten zijn vereist voor berekening.");
        }

        var result = _energyCalculationService.CalculateEnergy(data, provider); 
        return Ok(result);
    }

    [HttpPost("posttodatabase/{provider}")]
    public async Task<IActionResult> PostToDatabase([FromBody] ImportRequestDTO request, string provider, [FromQuery] int buildingId)
    {
        if (request == null || !request.Data.Any() || !ModelState.IsValid)
        {
            return BadRequest("Geen of ongeldige data ontvangen.");
        }

        try
        {
            var cumulativeValues = _importCalculator.CalculateImport(request.Data, provider);

            var filteredData = await _dateFilterService.FilterExistingDatesAsync(cumulativeValues, buildingId);

            await _usageDataRepository.BulkInsertAsync(filteredData, buildingId, request.CustomBattery);

            return Ok("Data succesvol geupload. Je ontvangt binnen 10 minuten een email met daarin je adviesrapport!");
        }
        catch (Exception ex)
        {
            return StatusCode(500, ex.Message);
        }

    }
}
