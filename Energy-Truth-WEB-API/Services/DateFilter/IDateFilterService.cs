using Energy_Truth.Shared.DTO_s;

namespace Energy_Truth_WEB_API.Services.DateFilter
{
    public interface IDateFilterService
    {
        Task<IEnumerable<UsageDataDTO>> FilterExistingDatesAsync(IEnumerable<UsageDataDTO> usageDataList, int buildingId);
    }
}
