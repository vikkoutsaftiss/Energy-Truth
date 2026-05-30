using Energy_Truth.Shared.Repositories;
using Infrastructure.DataAccess.DBContext;
using Infrastructure.DataAccess.Entities;
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
                Status = "importing",
                BuildingId = buildingId,
                ImportedAt = DateTime.UtcNow
            };
            _dbContext.ImportBatches.Add(importBatch);
            await _dbContext.SaveChangesAsync();
            return importBatch.ImportBatchId;
        }

        public async Task UpdateStatusBatchAsync(int importBatchId)
        {
            var batch = await _dbContext.ImportBatches.FindAsync(importBatchId);
            if (batch != null)
            {
                batch.Status = "ready";
                await _dbContext.SaveChangesAsync();
            }
        }
    }
}
