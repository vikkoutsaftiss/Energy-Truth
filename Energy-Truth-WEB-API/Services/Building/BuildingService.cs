using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;
using Microsoft.Identity.Client;

namespace Energy_Truth_WEB_API.Services.Building
{
    public class BuildingService : IBuildingService
    {
        private readonly IBuildingRepository _buildingRepository;

        public BuildingService(IBuildingRepository buildingRepository)
        {
            _buildingRepository = buildingRepository;
        }

        public async Task<int> CreateBuildingAsync(BuildingDTO buildingDTO)
        {
            var existingBuildingId = await GetBuildingIdByPostalCodeAndCustomerIdAsync(buildingDTO.PostalCode, buildingDTO.CustomerId);
            if (existingBuildingId != 0)
            {
                throw new InvalidOperationException("Dit gebouw bestaat al in jouw profiel.");

            }
            var buildingId = await _buildingRepository.CreateBuildingAsync(buildingDTO);
            return buildingId;
        }

        public async Task<int> GetBuildingIdByPostalCodeAndCustomerIdAsync(string postalCode, int customerId)
        {
            var buildingId = await _buildingRepository.GetBuildingIdByPostalCodeAndCustomerIdAsync(postalCode, customerId);
            return buildingId;
        }

        public async Task<List<BuildingDTO>> GetBuildingsByCustomerIdAsync(int customerId)
        {
            List<BuildingDTO> buildingId = await _buildingRepository.GetBuildingIdsByCustomerIdAsync(customerId);
            return buildingId;
        }
    }
}
