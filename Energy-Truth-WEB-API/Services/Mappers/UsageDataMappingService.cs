using Energy_Truth.Shared;
using Energy_Truth.Shared.DTO_s;


namespace Energy_Truth_WEB_API.Services.Mappers
{
    public class UsageDataMappingService
    {
        public IEnumerable<UsageDataDTO> MapToUsageDataDTOs(IEnumerable<EnergyImportDTO> inputModels, string provider)
        {
            return inputModels.Select(input => new UsageDataDTO
            {
                UsageMoment = input.Time,
                SourceData = provider,
                KWhBought = Convert.ToDecimal(input.ImportT1),
                KWhSold = Convert.ToDecimal(input.ExportT1)
            });
        }
    }
}
