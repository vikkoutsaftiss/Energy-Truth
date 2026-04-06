using Energy_Truth.Shared;
using Energy_Truth_WEB_API;
using Energy_Truth_WEB_API.Services;
using Microsoft.AspNetCore.Mvc;

[ApiController]
[Route("api/[controller]")] // Dit zorgt dat de URL /api/import wordt
public class ImportController : ControllerBase
{
    private readonly ImportService _importService;
    private readonly EnergyCalculationService _energyCalculationService;

    // De "Constructor": ASP.NET vult deze automatisch in
    public ImportController(ImportService importService, EnergyCalculationService energyCalculationService)
    {
        _importService = importService;
        _energyCalculationService = energyCalculationService;
    }

    [HttpPost("csv")]
    public IActionResult UploadCsv(IFormFile file)
    {
        if (file == null || file.Length == 0)
            return BadRequest("Geen bestand geselecteerd.");

        //var extension = Path.GetExtension(file.FileName).ToLower();
        //if (extension != ".csv")
        //    return BadRequest("Alleen CSV-bestanden zijn toegestaan.");

        //if (file.Length > 10 * 1024 * 1024)
        //    return BadRequest("Bestand is te groot. Maximaal 10 MB.");

        using var stream = file.OpenReadStream();

        // Hier roepen we jouw service aan!
        var resultaat = _importService.ProcessCsv(stream);

        // Voor nu sturen we de data gewoon terug als test
        return Ok(resultaat);
    }

    [HttpPost("calculate")]
    public IActionResult Calculate([FromBody] List<EnergyImportDTO> data)
    {
        if (data == null || !data.Any()) return BadRequest("Geen data ontvangen.");

        var result = _energyCalculationService.CalculateEnergy(data);
        return Ok(result);
    }
}
