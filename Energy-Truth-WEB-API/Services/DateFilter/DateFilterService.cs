using Energy_Truth.Shared.Repositories;
using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Services.DateFilter
{
    public class DateFilterService : IDateFilterService
    {
        private readonly IUsageDataRepository _usageDataRepository;

        public DateFilterService(IUsageDataRepository usageDataRepository)
        {
            _usageDataRepository = usageDataRepository;
        }

        public async Task<IEnumerable<UsageDataDTO>> FilterExistingDatesAsync(IEnumerable<UsageDataDTO> usageDataList, int buildingId)
        {
            var existingTimestamps = await _usageDataRepository.GetExistingTimestampsAsync(buildingId);

            var filteredList = usageDataList.Where(u => !existingTimestamps.Contains(u.UsageMoment));
            return filteredList;
        }
    }
}
