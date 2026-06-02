using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;
using Infrastructure.DataAccess.DBContext;
using Infrastructure.DataAccess.Entities;
using Microsoft.EntityFrameworkCore;
using Energy_Truth.Shared.Extensions;

namespace Infrastructure.DataAccess
{
    public class BuildingRepository : IBuildingRepository
    {
        private readonly EnergyDbContext _dbContext;

        public BuildingRepository(EnergyDbContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<int> CreateBuildingAsync(BuildingDTO buildingDTO)
        {
            var newBuilding = new Building
            {
                CustomerId = buildingDTO.CustomerId,
                PostalCode = buildingDTO.PostalCode,
                ConstructionYear = buildingDTO.ConstructionYear,
                ISTEnergyLabel = buildingDTO.ISTEnergyLabel
            };
            _dbContext.Buildings.Add(newBuilding);
            await _dbContext.SaveChangesAsync();
            return newBuilding.Id;
        }

        public async Task<int> GetBuildingIdByPostalCodeAndCustomerIdAsync(string postalCode, int customerId)
        {
            var buildingId = await _dbContext.Buildings.Where(b => b.PostalCode == postalCode && b.CustomerId == customerId)
                .Select(b => b.Id).FirstOrDefaultAsync();

            return buildingId;
        }

        public async Task<List<BuildingDTO>> GetBuildingIdsByCustomerIdAsync(int customerId)
        {
            List<BuildingDTO> buildings = await _dbContext.Buildings.Where(b => b.CustomerId == customerId)
                .Select(b => new BuildingDTO
                {
                    Id = b.Id,
                    CustomerId = b.CustomerId,
                    PostalCode = b.PostalCode,
                    ConstructionYear = b.ConstructionYear,
                    ISTEnergyLabel = b.ISTEnergyLabel
                }).ToListAsync();

            return buildings;
        }
    }
}
