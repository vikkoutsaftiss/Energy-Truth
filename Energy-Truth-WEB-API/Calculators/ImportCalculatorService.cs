using Energy_Truth.Shared;
using Energy_Truth.Shared.DTO_s;
using Energy_Truth.Shared.Providers;
using Energy_Truth.Shared.Repositories;

namespace Energy_Truth_WEB_API.Calculators
{
    public class ImportCalculatorService : IImportCalculator
    {
        private readonly IEnumerable<IEnergyProvider> _energyProviders;

        public ImportCalculatorService(IEnumerable<IEnergyProvider> energyProviders)
        {
            _energyProviders = energyProviders;
        }       

        public IEnumerable<UsageDataDTO> CalculateImport(List<EnergyImportDTO> data, string providerName)
        {
            var provider = _energyProviders.FirstOrDefault(p => p.Name == providerName);

            return provider?.IsCumulative ?? true
                ? CalculateCumulativeImport(data, providerName)
                : MapDirectImport(data, providerName);
        }

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

                if (cumulativeDTO.KWhBought > 15 || cumulativeDTO.KWhSold > 15)
                    continue;

                list.Add(cumulativeDTO);
            }
            return list;
        }

        public IEnumerable<UsageDataDTO> MapDirectImport(List<EnergyImportDTO> data, string provider)
        {
            var lastDate = data.Max(d => d.Time.Date);
            data = data.Where(d => d.Time.Date < lastDate).ToList();

            return data
                .Where(d => d.ImportT1 != null || d.ImportT2 != null || d.ExportT1 != null || d.ExportT2 != null)
                .Select(d => new UsageDataDTO
                {
                    KWhBought = Convert.ToDecimal((d.ImportT1 ?? 0) + (d.ImportT2 ?? 0)),
                    KWhSold = Convert.ToDecimal((d.ExportT1 ?? 0) + (d.ExportT2 ?? 0)),
                    UsageMoment = DateTime.SpecifyKind(d.Time, DateTimeKind.Utc),
                    SourceData = provider
                })
                .Where(d => d.KWhBought >= 0 && d.KWhSold >= 0)
                .Where(d => d.KWhBought <= 50 && d.KWhSold <= 50);
        }
    }
}
