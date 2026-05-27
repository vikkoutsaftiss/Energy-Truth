using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth.Shared.Repositories
{
    public interface IBuildingRepository
    {
        Task<int> GetBuildingIdAsync(string postalCode, int customerId);
        Task<int> CreateBuildingAsync(BuildingDTO buildingDTO);
    }
}
