using Energy_Truth.Shared.DTO_s;
using System;
using System.Collections.Generic;
using System.Text;

namespace Energy_Truth.Shared.Repositories
{
    public interface IImportBatchRepository
    {
        Task<int> CreateImportBatchAsync(int buildingId, CustomBatteryDTO customBattery);
        Task UpdateStatusBatchAsync(int importBatchId);

    }
}
