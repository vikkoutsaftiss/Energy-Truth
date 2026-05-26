using Energy_Truth.Shared.Repositories;
using System;
using System.Collections.Generic;
using System.Text;

namespace Infrastructure.DataAccess
{
    public class ImportBatchRepository : IImportBatchRepository
    {
        private readonly EnergyDbContext _dbContext;
        public ImportBatchRepository(EnergyDbContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<int> CreateImportBatchAsync(int buildingId)
        {
            var importBatch = new ImportBatch
            {
                BuildingId = buildingId,
                ImportedAt = DateTime.UtcNow
            };
            _dbContext.ImportBatches.Add(importBatch);
            await _dbContext.SaveChangesAsync();
            return importBatch.ImportBatchId;
        }
    }
}
