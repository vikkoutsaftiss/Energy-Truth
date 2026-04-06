using Energy_Truth.Shared;
using Microsoft.AspNetCore.Mvc;
using Postgrest;

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
                    .Order("valid_from", Postgrest.Constants.Ordering.Descending)
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
                // We halen de rauwe response op
                var response = await _supabase.From<ProviderDTO>().Get();

                // Als er een fout is in de response zelf
                if (response.ResponseMessage != null && !response.ResponseMessage.IsSuccessStatusCode)
                {
                    return StatusCode((int)response.ResponseMessage.StatusCode, response.Content);
                }

                // We sturen de RAUWE JSON tekst direct terug naar de browser/Scalar
                // Dit negeert alle C# class mapping problemen
                return Content(response.Content, "application/json");
            }
            catch (Exception ex)
            {
                return BadRequest($"API Fout: {ex.Message}");
            }
        }
    }
}
