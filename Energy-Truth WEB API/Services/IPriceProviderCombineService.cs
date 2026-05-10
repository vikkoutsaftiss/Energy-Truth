using Energy_Truth.Shared;

namespace Energy_Truth_WEB_API.Services
{
    public interface IPriceProviderCombineService
    {
        Task<List<ProviderPricingDTO>> Combine();
    }
}
