//using Energy_Truth.Shared;
//using Energy_Truth_WEB_API.Services;
//using Microsoft.AspNetCore.Mvc;
//using Supabase.Postgrest;

//namespace Energy_Truth_WEB_API.Controllers
//{
//    [ApiController]
//    [Route("api/[controller]")]
//    public class PriceController : ControllerBase
//    {
//        private readonly IPriceService _priceService;
//        private readonly IProviderService _providerService;

//        public PriceController(IPriceService priceService, IProviderService providerService)
//        {
//            _priceService = priceService;
//            _providerService = providerService;
//        }

//        [HttpGet("hourly")]
//        public async Task<IActionResult> GetHourlyPrices()
//        {
//            try
//            {
//                var response = await _priceService.GetCurrentPriceAsync();

//                return Ok(response);
//            }
//            catch (Exception ex)
//            {
//                return BadRequest(ex.Message);
//            }
//        }

//        [HttpGet("providers")]
//        public async Task<IActionResult> GetProviders()
//        {
//            try
//            {
//                var response = await _providerService.GetProvidersAsync();

//                return Ok(response);
//            }
//            catch (Exception ex)
//            {
//                return BadRequest($"API Fout: {ex.Message}");
//            }
//        }
//    }
//}
