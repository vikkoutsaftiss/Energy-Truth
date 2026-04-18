using Energy_Truth.Shared;
using Microsoft.AspNetCore.Mvc;
using Supabase.Postgrest;

namespace Energy_Truth_WEB_API.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class PriceController : ControllerBase
    {
        private readonly Supabase.Client _supabase;

        public PriceController(Supabase.Client supabase)
        {
            _supabase = supabase;
        }

        [HttpGet("hourly")]
        public async Task<IActionResult> GetHourlyPrices()
        {
            try
            {
                var response = await _supabase
                    .From<PriceDTO>()
                    .Order("valid_from", Supabase.Postgrest.Constants.Ordering.Descending)
                    .Get();

                return Content(response.Content, "application/json");
            }
            catch (Exception ex)
            {
                return BadRequest(ex.Message);
            }
        }

        [HttpGet("providers")]
        public async Task<IActionResult> GetProviders()
        {
            try
            {
                var response = await _supabase.From<ProviderDTO>().Get();

                if (response.ResponseMessage != null && !response.ResponseMessage.IsSuccessStatusCode)
                {
                    return StatusCode((int)response.ResponseMessage.StatusCode, response.Content);
                }
              
                return Content(response.Content, "application/json");
            }
            catch (Exception ex)
            {
                return BadRequest($"API Fout: {ex.Message}");
            }
        }
    }
}
