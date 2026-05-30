using Energy_Truth.Shared.Repositories;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Energy_Truth_WEB_API.Services.Building;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class BuildingController : ControllerBase
    {
        private readonly IBuildingService _buildingService;

        public BuildingController(IBuildingService buildingService)
        {
            _buildingService = buildingService;
        }

        [HttpPost("createbuilding")]
        public async Task<IActionResult> CreateBuilding([FromBody] BuildingDTO buildingDTO)
        {
            if (buildingDTO == null)
            {
                return BadRequest("Ongeldige gebouwgegevens.");
            }
            if (string.IsNullOrEmpty(buildingDTO.PostalCode))
            {
                return BadRequest("Postcode is verplicht.");
            }
            if (buildingDTO.CustomerId <= 0)
            {
                return BadRequest("Ongeldige klant ID.");
            }
            try
            {
                var buildingId = await _buildingService.CreateBuildingAsync(buildingDTO);
                return Ok(buildingId);
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Er is een fout opgetreden bij het aanmaken van het gebouw: {ex.Message}");
            }
        }

        [HttpGet("getbuildingsbycustomerid/{customerId}")]
        public async Task<IActionResult> GetBuildingByCustomerId(int customerId)
        {
            if (customerId <= 0)
            {
                return BadRequest("Ongeldige klant ID.");
            }
            try
            {
                List<BuildingDTO> buildings = await _buildingService.GetBuildingsByCustomerIdAsync(customerId);
                if (buildings != null)
                {
                    return Ok(buildings);
                }
                else
                {
                    return NotFound("Geen gebouw gevonden voor deze klant en postcode.");
                }
            }
            catch (Exception ex)
            {
                return StatusCode(500, $"Er is een fout opgetreden bij het ophalen van het gebouw: {ex.Message}");
            }
        }
    }
}
