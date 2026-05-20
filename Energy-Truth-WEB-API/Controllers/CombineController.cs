using Energy_Truth_WEB_API.Services;
using Microsoft.AspNetCore.Mvc;

namespace Energy_Truth_WEB_API.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class CombineController : ControllerBase
    {
        private readonly IPriceProviderCombineService _priceProviderCombineService;

        public CombineController(IPriceProviderCombineService priceProviderCombineService)
        {
            _priceProviderCombineService = priceProviderCombineService;
        }

        [HttpGet]
        public async Task<IActionResult> Combine()
        {
            var combinedResult = await _priceProviderCombineService.Combine();
            return Ok(combinedResult);
        }
    }
}
