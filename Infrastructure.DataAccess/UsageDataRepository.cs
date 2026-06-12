using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;
using Microsoft.EntityFrameworkCore;
using EFCore.BulkExtensions;
using Infrastructure.DataAccess.DBContext;
using Infrastructure.DataAccess.Entities;

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

        public async Task<int> BulkInsertAsync(IEnumerable<UsageDataDTO> usageDataList, int buildingId, CustomBatteryDTO customBattery)
        {
            using var transaction = await _dbContext.Database.BeginTransactionAsync();
            try
            {
                var importBatchId = await _importBatchRepository.CreateImportBatchAsync(buildingId, customBattery);

                await _dbContext.BulkInsertAsync(usageDataList.Select(u => new UsageData
                {
                    ImportBatchId = importBatchId,
                    UsageMoment = u.UsageMoment,
                    SourceData = u.SourceData,
                    KWhBought = u.KWhBought,
                    KWhSold = u.KWhSold
                }).ToList());

                await _importBatchRepository.UpdateStatusBatchAsync(importBatchId);

                await transaction.CommitAsync();
                return importBatchId;
            }
            catch (Exception)
            {
                await transaction.RollbackAsync();
                throw;
            }
        }

        public async Task<HashSet<DateTime>> GetExistingTimestampsAsync(int buildingId)
        {
            var existingTimestamps = await _dbContext.UsageData
                .Where(u => u.ImportBatch.BuildingId == buildingId)
                .Select(u => u.UsageMoment)
                .ToHashSetAsync();

            return existingTimestamps;
        }


    }
}
