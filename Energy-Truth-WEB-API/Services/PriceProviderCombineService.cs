using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Services
{
    public class PriceProviderCombineService : IPriceProviderCombineService
    {
        private readonly IProviderService _providerService;
        private readonly IPriceService _priceService;

        public PriceProviderCombineService(IProviderService providerService, IPriceService priceService)
        {
            _providerService = providerService;
            _priceService = priceService;
        }

        public async Task<List<ProviderPricingDTO>> Combine()
        {
            var providerData = await _providerService.GetProvidersAsync();
            var priceData = await _priceService.GetCurrentPriceAsync();

            var combined = providerData.Join(
                priceData, 
                providerData => providerData.Code,
                priceData => priceData.ProviderCode,
                (providerData, priceData) => new ProviderPricingDTO
                {
                    ProviderName = providerData.Name,
                    ProviderCode = providerData.Code,
                    Price = priceData.Price,
                    ValidFrom = priceData.ValidFrom
                })
                .GroupBy(x => x.ProviderCode)
                .Select(g => g.OrderByDescending(x => x.ValidFrom).First())
                .OrderBy(x => x.ProviderName)
                .ToList();

            return combined;
        }
    }
}
