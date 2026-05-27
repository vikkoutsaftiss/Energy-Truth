using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Services.Building
{
    public interface IBuildingService
    {
        Task<int> CreateOrGetBuildingAsync(BuildingDTO buildingDTO);
        Task<int> GetBuildingIdAsync(string postalCode, int customerId);
    }
}
