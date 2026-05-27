using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Services.Building
{
    public class BuildingService : IBuildingService
    {
        private readonly IBuildingRepository _buildingRepository;

        public BuildingService(IBuildingRepository buildingRepository)
        {
            _buildingRepository = buildingRepository;
        }

        public async Task<int> CreateOrGetBuildingAsync(BuildingDTO buildingDTO)
        {
            var existingBuildingId = await GetBuildingIdAsync(buildingDTO.PostalCode, buildingDTO.CustomerId);
            if (existingBuildingId != 0)
            {
                return existingBuildingId;
            }
            var buildingId = await _buildingRepository.CreateBuildingAsync(buildingDTO);
            return buildingId;
        }

        public async Task<int> GetBuildingIdAsync(string postalCode, int customerId)
        {
            var buildingId = await _buildingRepository.GetBuildingIdAsync(postalCode, customerId);
            return buildingId;
        }
    }
}
