using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Services.Building
{
    public interface IBuildingService
    {
        Task<int> CreateBuildingAsync(BuildingDTO buildingDTO);
        Task<int> GetBuildingIdByPostalCodeAndCustomerIdAsync(string postalCode, int customerId);
        Task<List<BuildingDTO>> GetBuildingsByCustomerIdAsync(int customerId);

    }
}
