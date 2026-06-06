using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Energy_Truth_WEB_API.Services.Battery;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth_WEB_API.Services.Customer;

namespace Energy_Truth_WEB_API.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    public class BatteryController : ControllerBase
    {
        private readonly IBatteryService _batteryService;
        private readonly ICustomerService _customerService;

        public BatteryController(IBatteryService batteryService, ICustomerService customerService)
        {
            _batteryService = batteryService;
            _customerService = customerService;
        }
       
        [HttpGet("getbatteries")]
        public async Task<IActionResult> GetBatteries()
        {
            //if (!await IsAdminAsync()) return Unauthorized();

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

        [HttpPut("updatebattery/{id}")]
        public async Task<IActionResult> UpdateBattery(int id, [FromBody] BatteryDTO batteryDto)
        {
            try
            {
                bool result = await _batteryService.UpdateBatteryAsync(id, batteryDto);
                if (result)
                {
                    return NoContent();
                }
                else
                {
                    return NotFound();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(ex.Message);
                return StatusCode(500, ex.Message); // tijdelijk, niet in productie
            }
        }

        [HttpPost("createbattery")]
        public async Task<IActionResult> CreateBattery([FromBody] BatteryDTO batteryDto)
        {
            try
            {
                var result = await _batteryService.CreateBatteryAsync(batteryDto);
                if (result != null)
                {
                    return Ok(batteryDto);
                }
                else
                {
                    return BadRequest();
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine(ex.Message);
                return BadRequest();
            }
        }

        private async Task<bool> IsAdminAsync()
        {
            if (!Request.Headers.TryGetValue("X-Customer-Id", out var value)) return false;
            if (!int.TryParse(value, out int customerId)) return false;
            return await _customerService.IsAdminAsync(customerId);
        }
    }
}
