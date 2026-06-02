using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Energy_Truth_WEB_API.Services.Battery;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class BatteryController : ControllerBase
    {
        private readonly IBatteryService _batteryService;

        public BatteryController(IBatteryService batteryService)
        {
            _batteryService = batteryService;
        }

        [HttpGet("getbatteries")]
        public async Task<IActionResult> GetBatteries()
        {
            try
            {
                List<BatteryDTO> batteries = await _batteryService.GetBatteriesAsync();
                return Ok(batteries);
            }
            catch (Exception ex)
            {
                Console.WriteLine(ex.Message);
                return StatusCode(500, ex.Message); // tijdelijk, niet in productie
            }
        }
    }
}
