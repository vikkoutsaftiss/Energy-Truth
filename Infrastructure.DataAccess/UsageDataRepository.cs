using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;
using Microsoft.EntityFrameworkCore;
using EFCore.BulkExtensions;
namespace Infrastructure.DataAccess
{
    public class UsageDataRepository : IUsageDataRepository
    {
        private readonly EnergyDbContext _dbContext;
        private readonly IImportBatchRepository _importBatchRepository;

        public UsageDataRepository(EnergyDbContext dbContext, IImportBatchRepository importBatchRepository)
        {
            _dbContext = dbContext;
            _importBatchRepository = importBatchRepository;
        }

        public async Task<int> BulkInsertAsync(IEnumerable<UsageDataDTO> usageDataList, int buildingId)
        {
            var importBatchId = await _importBatchRepository.CreateImportBatchAsync(buildingId);

            await _dbContext.BulkInsertAsync(usageDataList.Select(u => new UsageData
            {
                BuildingId = buildingId,
                ImportBatchId = importBatchId,
                UsageMoment = u.UsageMoment,
                SourceData = u.SourceData,
                KWhBought = u.KWhBought,
                KWhSold = u.KWhSold
            }).ToList());

            return importBatchId;
        }
    }
}
