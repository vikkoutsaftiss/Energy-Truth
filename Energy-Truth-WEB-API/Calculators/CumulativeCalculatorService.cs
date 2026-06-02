using Energy_Truth.Shared;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Repositories;

namespace Energy_Truth_WEB_API.Calculators
{
    public class CumulativeCalculatorService : ICumulativeCalculator
    {
        public IEnumerable<UsageDataDTO> CalculateCumulativeImport(List<EnergyImportDTO> data, string provider)
        {
            var list = new List<UsageDataDTO>();

            var lastDate = data.Max(d => d.Time.Date);
            data = data.Where(d => d.Time.Date < lastDate).ToList();

            for (int i = 1; i < data.Count; i++)
            {
                var currentDataPoint = data[i];
                var previousDataPoint = data[i - 1];

                if (currentDataPoint.ImportT1 == null && currentDataPoint.ImportT2 == null &&
                    currentDataPoint.ExportT1 == null && currentDataPoint.ExportT2 == null)
                    continue;

                var cumulativeDTO = new UsageDataDTO
                {
                    KWhBought = Convert.ToDecimal((currentDataPoint.ImportT1 ?? 0) + (currentDataPoint.ImportT2 ?? 0)) - Convert.ToDecimal((previousDataPoint.ImportT1 ?? 0) + (previousDataPoint.ImportT2 ?? 0)),
                    KWhSold = Convert.ToDecimal((currentDataPoint.ExportT1 ?? 0) + (currentDataPoint.ExportT2 ?? 0)) - Convert.ToDecimal((previousDataPoint.ExportT1 ?? 0) + (previousDataPoint.ExportT2 ?? 0)),
                    UsageMoment = DateTime.SpecifyKind(currentDataPoint.Time, DateTimeKind.Utc),
                    SourceData = provider
                };

                if (cumulativeDTO.KWhBought < 0 || cumulativeDTO.KWhSold < 0)
                    continue;

                list.Add(cumulativeDTO);
            }
            return list;
        }
    }
}
