using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth.Shared.Repositories
{
    public interface IUsageDataRepository
    {
        Task<int> BulkInsertAsync(IEnumerable<UsageDataDTO> usageDataList, int buildingId);
        Task<HashSet<DateTime>> GetExistingTimestampsAsync(int buildingId);
    }
}
